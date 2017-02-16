# -*- coding: utf-8 -*-
import sublime, sublime_plugin
import os
import re

var_pattern = re.compile(r"^(\w+)\s*=")
fun_pattern = re.compile(r"^function\s*(\w+)\s*\(([\w\s,]*)\)")
class_pattern = re.compile(r"(\w+)\s*=\s*class\(.*,\s*(\w+)\s*\)")
interface_pattern = re.compile(r"^implement\(\s*(\w+)\s*,(.*)\)")
cls_var_pattern = re.compile(r"self\.(\w+)\s*=")
cls_fun_pattern = re.compile(r"^function\s+(\w+)[\.:](\w+)\s*\(([\w,\s]*)\)")
require_pattern = re.compile(r"""(\w+)\s*=\s*require\s*\(?\s*["']([\w\.]+)""")

indices = {} # path -> variables
classes_info = {}

BUILTIN_MODULES = {
	"coroutine" : ("create", "resume", "running", "status", "wrap", "yield"),
	"string"	: ("byte", "char", "dump", "find", "format", "gmatch", "gsub", "len", "lower", "match", "rep", "reverse", "sub", "upper"),
	"table" 	: ("concat", "insert", "maxn", "remove", "sort"),
	"math" 		: ("abs", "acos", "asin", "atan", "atan2", "ceil", "cos", "cosh", "deg", "exp", "floor", "fmod",
					"frexp", "ldexp", "log", "log10", "max", "min", "modf", "pow", "rad", "random", "randomseed", "sin", "sinh", "sqrt", "tan", "tanh", "pi"),
	"io" 		: ("close", "flush", "input", "lines", "open", "output", "popen", "read", "tmpfile", "type", "write"),
	"os" 		: ("clock", "date", "difftime", "execute", "exit", "getenv", "remove", "rename", "setlocale", "time", "tmpname"),
	"package" 	: ("cpath", "loaded", "loadlib", "path", "preload", "seeall"),
	"debug" 	: ("debug", "getfenv", "setfenv", "gethook", "sethook", "getinfo", "getlocal", "setlocal",
					"getmetatable", "setmetatable", "getregistry", "getupvalue", "setupvalue", "traceback"),
}

def index_module(view, location, content):
	if len(indices) == 0:
		generate_indices()

	# find whole word
	pos = view.find_by_class(location, False, sublime.CLASS_WORD_START, " ")
	if pos <= 0: return None

	word = view.substr(sublime.Region(pos, location))
	names = word.replace(':', '.').split('.')
	if len(names) != 2: return None

	first_name = names[0]

	if first_name in BUILTIN_MODULES:
		return index_builtin(first_name)

	module_path = to_local_path(view.file_name())
	if module_path is None:
		print("Failed get local path")
		return None

	indexer = LuaIndexer(module_path, location)
	indexer.parse_content(content)

	return indexer.index_value(first_name)


def index_builtin(key):
	methods = BUILTIN_MODULES[key]
	return [[name + "\t" + key, name] for name in methods]

def collect_bases(bases, cpath):
	bases.add(cpath)

	cls_info = classes_info.get(cpath)
	if cls_info is None: return

	for base in cls_info.get(".bases", ()):
		if base not in bases:
			collect_bases(bases, base)

def to_local_path(full_path):
	for proj_data in sublime.active_window().project_data()["folders"]:
		proj_dir = proj_data["path"]
		lua_paths = proj_data.get("lua_paths", ())
		for lpath in lua_paths:
			cur_path = os.path.join(proj_dir, lpath)
			if not os.path.isdir(cur_path): continue

			relative_path = os.path.relpath(full_path, cur_path)
			if relative_path[0] != '.':
				name = relative_path.split('.')[0]
				return name.replace("/", ".").replace("\\", ".")

	return None

def generate_indices():
	print("generate lua project indices.")
	global indices
	indices = {"_G" : [["_G", "_G"]] }

	global classes_info
	classes_info = {}

	window = sublime.active_window()
	for proj_data in window.project_data()["folders"]:
		proj_dir = proj_data["path"]
		lua_paths = proj_data.get("lua_paths")
		if lua_paths is None:
			sublime.error_message("please set 'lua_paths' in project setting file.")
			continue

		for lpath in lua_paths:
			cur_path = os.path.join(proj_dir, lpath)
			if not os.path.exists(cur_path) or not os.path.isdir(cur_path):
				continue

			gen_indices_in_path(cur_path)

	return


def gen_indices_in_path(path):
	print("parse lua:", path)
	for root, dirs, files in os.walk(path):
		for fname in files:
			name, ext = os.path.splitext(fname)
			if ext != ".lua": continue

			key = os.path.relpath(root, path)
			key = key.replace('\\', '.').replace('/', '.')
			key += "." + name

			indexer = LuaIndexer(key)
			indexer.parse_file(os.path.join(root, fname))

	return


class LuaIndexer:
	def __init__(self, module_name, location = 0):
		super(LuaIndexer, self).__init__()
		self.module_name = module_name

		self.requires = {}
		self.module = {}
		self.classes = {}

		self.location = location
		self.pos = 0

		self.last_cname = None
		self.self_cname = None

	def flush(self):
		for cname, cls_info in self.classes.items():
			self.module[cname + "\tclass"] = cname

			cpath = self.module_name + "." + cname
			indices[cpath] = cls_info

		indices[self.module_name] = self.module


	def parse_file(self, path, encoding = "utf-8"):
		with open(path, "r", encoding = encoding) as f:
			for line in f.readlines():
				self.pos += len(line)
				self.parse_line(line)

		self.flush()

	def parse_content(self, content):
		for line in content.split('\n'):
			self.pos += len(line) + 1
			self.parse_line(line)

		self.flush()

	def parse_line(self, line):
		match = var_pattern.match(line)
		if match:
			var = match.group(1)
			self.module[var + "\tvar"] = var
			return

		match = fun_pattern.match(line)
		if match:
			var = match.group(1)
			args = match.group(2)
			self.module[var + "\tfunction"] = var + "($0%s)" % args
			return

		match = require_pattern.search(line)
		if match:
			var, path = match.group(1), match.group(2)
			self.requires[var] = path
			return

		# parse class defination
		match = class_pattern.search(line)
		if match:
			cname, base_name = match.group(1), match.group(2)
			cname = self.module_name + "." + cname

			base_path = self.find_base_class_path(base_name)
			if base_path is None:
				print("Failed find base class:", cname, base_name)
				return

			cls_info = classes_info.setdefault(cname, {})
			cls_info[".bases"] = [base_path, ]
			return

		# parse class implement interfaces
		match = interface_pattern.match(line)
		if match:
			cname, args = match.group(1), match.group(2)
			cname = self.module_name + "." + cname

			bases = []
			for base_name in args.split(','):
				base_name = base_name.strip()
				if len(base_name) == 0: continue

				base_path = self.find_base_class_path(base_name)
				if base_path is None:
					print("Failed find base class:", cname, base_name)
					continue

				bases.append(base_path)

			cls_info = classes_info.setdefault(cname, {})
			cls_info.setdefault(".bases", []).extend(bases)
			return

		if self.last_cname is not None:
			match = cls_var_pattern.search(line)
			if match:
				var = match.group(1)
				cls_info = self.classes[self.last_cname]
				cls_info[var + "\tvar"] = var
				return

		match = cls_fun_pattern.match(line)
		if match:
			cname, var, args = match.group(1), match.group(2), match.group(3)
			cls_info = self.classes.setdefault(cname, {})
			cls_info[var + "\tfunction"] = "%s($0%s)" % (var, args)
			self.last_cname = cname
			if self.pos < self.location:
				self.self_cname = cname

		return

	def find_base_class_path(self, base_name):
		# find base class from external module
		base_path = self.requires.get(base_name)
		if base_path is None:
			# find base class in current module
			base_path = self.classes.get(base_name)
			if base_path is None:
				return # doesn't found

			base_path = self.module_name + "." + base_path
		else:
			base_name = base_path.split('.')[-1]
			base_path += "." + base_name

		return base_path

	def index_value(self, key):
		if key == "self":
			return self.index_self(), sublime.INHIBIT_WORD_COMPLETIONS

		ret = self.index_class(key)
		if ret: return ret, sublime.INHIBIT_WORD_COMPLETIONS

		ret = self.index_module(key)
		if ret: return ret, sublime.INHIBIT_WORD_COMPLETIONS

		return None

	def index_self(self):
		#print("class name", self.self_cname)
		if self.self_cname is None: return None

		cname = self.module_name + "." + self.self_cname

		bases = set()
		collect_bases(bases, cname)
		#print("bases", sorted(bases))

		values = {}
		for base in bases:
			fileds = indices.get(base)
			if fileds is None: continue

			values.update(fileds)

		return self.to_sorted_values(values)

	def index_class(self, key):
		cname = self.module_name + "." + key
		ret = self.index_class_by_cname(cname)
		if ret is not None: return ret

		# wheather key is an external class
		path = self.requires.get(key)
		if path is None: return None

		cname = path + "." + key
		return self.index_class_by_cname(cname)

	def index_class_by_cname(self, cname):
		#print("try class", cname)
		if cname not in classes_info: return None # not class

		bases = set()
		collect_bases(bases, cname)
		#print("bases", sorted(bases))

		values = {}
		for base in bases:
			fileds = indices.get(base)
			if fileds is None: continue

			for k, v in fileds.items():
				if "\tfunction" in k:
					values[k] = v

		return self.to_sorted_values(values)

	def index_module(self, key):
		path = self.requires.get(key)
		#print("module", path)
		if path is None: return None

		values = indices.get(path)
		return self.to_sorted_values(values)

	def to_sorted_values(self, symbols):
		if symbols is None: return None

		ret = list(symbols.items())
		ret.sort(key = lambda x: x[0])
		return ret


class LuaIndexProjectCommand(sublime_plugin.WindowCommand):
	def run(self):
		generate_indices()
		self.window.status_message("generate lua project index finished.")

