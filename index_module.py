# -*- coding: utf-8 -*-
import sublime, sublime_plugin
import os
import re

var_pattern = re.compile(r"^(\w+)\s*=")
fun_pattern = re.compile(r"^function\s*(\w+)\s*\(([\w\s,]*)\)")
cls_pattern = re.compile(r"(\w+)\s*=\s*class\(.*,\s*(\w+)\s*\)")
inf_pattern = re.compile(r"implement\(\s*(\w+)\s*(?:,\s*(\w+)\s*)+\)")
cls_var_pattern = re.compile(r"self\.(\w+)\s*=")
cls_fun_pattern = re.compile(r"^function\s+(\w+)[\.:](\w+)\s*\(([\w,\s]*)\)")

indices = {} # path -> variables

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
	if first_name == "self":
		return index_self(location, content)

	path = find_require_path(first_name, content)
	print("prefix", first_name, path)

	if path is None: return None

	return indices.get(path.replace("/", ".")), sublime.INHIBIT_WORD_COMPLETIONS

def index_self(location, content):
	pos = 0
	last_cname = None
	self_cname = None
	classes = {}
	for line in content.split('\n'):
		pos += len(line) + 1

		if last_cname:
			match = cls_var_pattern.search(line)
			if match:
				var = match.group(1)
				classes[last_cname][var + "\tvar"] = var
				continue

		match = cls_fun_pattern.match(line)
		if match:
			cname, var, args = match.group(1), match.group(2), match.group(3)
			classes.setdefault(cname, {})[var + "\tfunction"] = "%s($0%s)" % (var, args, )
			if pos < location:
				self_cname = cname
			last_cname = cname

	print("class name", self_cname)
	if self_cname is None: return None

	fileds = classes.get(self_cname)
	if fileds is None: return None

	values = list(fileds.items())
	values.sort(key = lambda x: x[0])
	return values

def generate_indices():
	print("generate lua project indices.")
	global indices
	indices = {}

	window = sublime.active_window()
	for proj_data in window.project_data()["folders"]:
		proj_dir = proj_data["path"]
		lua_paths = proj_data.get("lua_paths", ("", ))
		for lpath in lua_paths:
			cur_path = os.path.join(proj_dir, lpath)
			if not os.path.exists(cur_path) or not os.path.isdir(cur_path):
				continue

			gen_indices_in_path(cur_path)

	return


def gen_indices_in_path(path):
	for root, dirs, files in os.walk(path):
		for fname in files:
			name, ext = os.path.splitext(fname)
			if ext != ".lua": continue

			key = os.path.relpath(root, path)
			key = key.replace('\\', '.').replace('/', '.')
			key += "." + name
			gen_indices_in_file(key, os.path.join(root, fname))

	return

def gen_indices_in_file(key, path):
	module = {}
	classes = {}
	with open(path, "r", encoding="utf-8") as f:
		last_cname = None

		for line in f.readlines():
			match = var_pattern.match(line)
			if match:
				var = match.group(1)
				module[var + "\tvar"] = var
				continue

			match = fun_pattern.match(line)
			if match:
				var = match.group(1)
				args = match.group(2)
				module[var + "\tfunction"] = var + "($0%s)" % args
				continue

			if last_cname is not None:
				match = cls_var_pattern.search(line)
				if match:
					var = match.group(1)
					classes[last_cname][var + "\tvar"] = var
					continue

			match = cls_fun_pattern.match(line)
			if match:
				cname, var, args = match.group(1), match.group(2), match.group(3)
				classes.setdefault(cname, {})[var + "\tfunction"] = "%s($0%s)" % (var, args)
				last_cname = cname

	if len(module) > 0:
		values = [[k, v] for k, v in module.items()]
		values.sort(key = lambda x: x[1])
		indices[key] = values

	if len(classes) > 0:
		for cname, fileds in classes.items():
			values = [[k, v] for k, v in fileds.items()]
			values.sort(key = lambda x: x[1])
			indices[key + "." + cname] = values

	return

def find_require_path(name, content):
	pattern = r"""%s\s*=\s*require\s*\(?\s*["']([\w\.]+)""" % name
	match = re.search(pattern, content)
	return match.group(1) if match else None

class LuaIndexProjectCommand(sublime_plugin.WindowCommand):
	def run(self):
		generate_indices()
		self.window.status_message("generate lua project index finished.")

