# -*- coding: utf-8 -*-
import sublime, sublime_plugin
import os
import re
import imp
import json

var_pattern = re.compile(r"^(\w+)\s*=")
fun_pattern = re.compile(r"^function\s*(\w+)\s*\(([\w\s,]*)\)")
class_pattern = re.compile(r"(\w+)\s*=\s*class\(.*,\s*(\w+)\s*\)")
interface_pattern = re.compile(r"^implement\(\s*(\w+)\s*,(.*)\)")
cls_var_pattern = re.compile(r"self\.(\w+)\s*=")
cls_fun_pattern = re.compile(r"^function\s+(\w+)[\.:](\w+)\s*\(([\w,\s]*)\)")
require_pattern = re.compile(r"""(\w+)\s*=\s*require\s*\(?\s*["']([\w\.]+)""")

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

PROJECT_DATAS = {}

def index_module(view, location, content):
	# find whole word
	pos = view.find_by_class(location, False, sublime.CLASS_WORD_START, " ")
	if pos <= 0: return None

	word = view.substr(sublime.Region(pos, location))
	names = word.replace(':', '.').split('.')
	if len(names) != 2: return None

	first_name = names[0]

	if first_name in BUILTIN_MODULES:
		return index_builtin(first_name)

	proj_indexer = find_project_indexer(view.file_name())

	indexer = proj_indexer.find_file_indexer(view.file_name())
	if indexer is None:
		print("failed find file indexer")
		return

	indexer.parse_content(content)
	return indexer.index_value(first_name)


def index_builtin(key):
	methods = BUILTIN_MODULES[key]
	return [[name + "\t" + key, name] for name in methods]


def is_abs_path(path):
	if len(path) > 1 and path[0] == '/': return True
	if len(path) > 2 and path[1] == ':': return True
	return False

def load_python_file(path):
	module = {}
	with open(path, "r") as f:
		obj = compile(f.read(), path, "exec")
		exec(obj, globals(), module)
	return module

def get_all_project_paths():
	paths = []

	window = sublime.active_window()

	root_path = ""
	project_file_name = window.project_file_name()
	if project_file_name:
		root_path = os.path.dirname(project_file_name)

	for proj_data in window.project_data()["folders"]:
		proj_path = proj_data["path"]

		if not is_abs_path(proj_path):
			proj_path = os.path.normpath(os.path.join(root_path, proj_path))

		if not os.path.exists(proj_path):
			continue

		paths.append(proj_path)

	return paths

def generate_indices():
	print("generate lua project indices.")

	paths = get_all_project_paths()
	for project_path in paths:
		proj_indexer = ProjectIndexer(project_path)
		proj_indexer.generate_indices()

		PROJECT_DATAS[project_path] = proj_indexer

	print("finished in %d path" % len(paths))
	return

def find_project_indexer(file_name):
	for project_path in get_all_project_paths():
		if file_name.startswith(project_path):
			return get_or_load_project_indexer(project_path)
	return None

def get_or_load_project_indexer(project_path):
	proj_indexer = PROJECT_DATAS.get(project_path)
	if proj_indexer is None:
		
		proj_indexer = ProjectIndexer(project_path)
		proj_indexer.generate_indices()
		PROJECT_DATAS[project_path] = proj_indexer

	return proj_indexer

def path_to_module_name(path):
	return path.replace('\\', '.').replace('/', '.')

class ProjectIndexer(object):
	def __init__(self, project_path):
		self.project_path = project_path

		self.indices = {"_G" : [["_G", "_G"]] }
		self.classes_info = {}
		self.file_indexers = {}

		self.config_module = self.load_config_module()
		self.lua_paths = []

		self.parse_config()

	def generate_indices(self):
		for path in self.lua_paths:
			self.gen_indices_in_path(path)
		return

	def load_config_module(self):
		config_file = os.path.join(self.project_path, "lua-autocomplete.py")
		if not os.path.exists(config_file):
			return None

		return load_python_file(config_file)

	def parse_config(self):
		if not self.config_module:
			return

		for path in self.config_module["LUA_PATHS"]:
			lua_path = os.path.join(self.project_path, path)
			if not os.path.exists(lua_path) or not os.path.isdir(lua_path):
				continue

			self.lua_paths.append(lua_path)

		return

	def gen_indices_in_path(self, path):
		print("parse lua:", path)

		for root, dirs, files in os.walk(path):
			for fname in files:
				name, ext = os.path.splitext(fname)
				if ext != ".lua": continue

				fpath = os.path.join(root, name)
				fpath = os.path.relpath(fpath, path)
				module_name = path_to_module_name(fpath)

				indexer = FileIndexer(self, module_name)
				indexer.parse_file(os.path.join(root, fname))

				self.file_indexers[module_name] = indexer

		return

	def add_symbol(self, name, symbols):
		self.indices[name] = symbols

	def get_symbol(self, name):
		return self.indices.get(name)

	def get_or_add_class(self, class_name):
		return self.classes_info.setdefault(class_name, {})

	def get_class(self, class_name):
		return self.classes_info.get(class_name)

	def is_class(self, name):
		return name in self.classes_info

	def find_file_indexer(self, file_path):
		for lua_path in self.lua_paths:
			relative_path = os.path.relpath(file_path, lua_path)
			if relative_path[0] != '.':
				module_name = path_to_module_name(os.path.splitext(relative_path)[0])

				indexer = self.file_indexers.get(module_name)
				if indexer is None:
					indexer = FileIndexer(self, module_name)
					self.file_indexers[key] = indexer

				return indexer

		return None


class FileIndexer:
	def __init__(self, proj_indexer, module_name, location = 0):
		super(FileIndexer, self).__init__()
		self.proj_indexer = proj_indexer
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
			self.proj_indexer.add_symbol(cpath, cls_info)

		self.proj_indexer.add_symbol(self.module_name, self.module)


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

			cls_info = self.proj_indexer.get_or_add_class(cname)
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

			cls_info = self.proj_indexer.get_or_add_class(cname)
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
		self.collect_bases(bases, cname)
		#print("bases", sorted(bases))

		values = {}
		for base in bases:
			fileds = self.proj_indexer.get_symbol(base)
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
		if not self.proj_indexer.is_class(cname): return None

		bases = set()
		self.collect_bases(bases, cname)
		#print("bases", sorted(bases))

		values = {}
		for base in bases:
			fileds = self.proj_indexer.get_symbol(base)
			if fileds is None: continue

			for k, v in fileds.items():
				if "\tfunction" in k:
					values[k] = v

		return self.to_sorted_values(values)

	def index_module(self, key):
		path = self.requires.get(key)
		#print("module", path)
		if path is None: return None

		values = self.proj_indexer.get_symbol(path)
		return self.to_sorted_values(values)

	def to_sorted_values(self, symbols):
		if symbols is None: return None

		ret = list(symbols.items())
		ret.sort(key = lambda x: x[0])
		return ret


	def collect_bases(self, bases, cpath):
		bases.add(cpath)

		cls_info = self.proj_indexer.get_class(cpath)
		if cls_info is None: return

		for base in cls_info.get(".bases", ()):
			if base not in bases:
				self.collect_bases(bases, base)

		return


def write_debug_info():
	datas = {}

	for path, indexer in PROJECT_DATAS.items():
		datas[path] = {
			"indices" : indexer.indices,
			"classes" : indexer.classes_info,
		}

	temp_file = os.path.join(sublime.cache_path(), "lua-autocomplete-temp.json")
	with open(temp_file, "w") as f:
		json.dump(datas, f, indent = 4, sort_keys = True)

	print("write cache file", temp_file)

class LuaIndexProjectCommand(sublime_plugin.WindowCommand):
	def run(self):
		generate_indices()
		self.window.status_message("generate lua project index finished.")

		write_debug_info()

