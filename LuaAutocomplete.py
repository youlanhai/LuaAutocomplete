
import sublime, sublime_plugin
import re, os, itertools
from LuaAutocomplete.locals import LocalsFinder
from LuaAutocomplete import indexer

class LocalsAutocomplete(sublime_plugin.EventListener):
	@staticmethod
	def can_local_autocomplete(view, location):
		"""
		Returns true if locals autocompetion makes sense in the specified location (ex. its not indexing a variable, in a string, ...)
		"""
		pos = view.find_by_class(location, False, sublime.CLASS_WORD_START)
		if pos == 0:
			return True
		
		scope_name = view.scope_name(location)
		if "string." in scope_name or "comment." in scope_name:
			# In a string or comment
			return False
		
		if "parameter" in scope_name:
			# Specifying parameters
			return False
		
		char = view.substr(pos-1)
		if char == "." or char == ":":
			# Indexing a value
			return False
		
		return True
	
	def on_query_completions(self, view, prefix, locations):
		if view.settings().get("syntax") != "Packages/Lua/Lua.sublime-syntax":
			# Not Lua, don't do anything.
			return
		
		location = locations[0] # TODO: Better multiselect behavior?
		
		if not LocalsAutocomplete.can_local_autocomplete(view, location):
			return
		
		src = view.substr(sublime.Region(0, view.size()))

		results = indexer.index_module(view, location, src)
		if results is not None: return results
		
		localsfinder = LocalsFinder(src)
		varz = localsfinder.run(location)
		
		return [(name+"\t"+data.vartype,name) for name, data in varz.items()]

class RequireAutocomplete(sublime_plugin.EventListener):
	
	@staticmethod
	def filter_lua_files(filenames):
		for f in filenames:
			fname, ext = os.path.splitext(f)
			if ext == ".lua" or ext == ".luac":
				yield fname
	
	def on_query_completions(self, view, prefix, locations):
		if view.settings().get("syntax") != "Packages/Lua/Lua.sublime-syntax":
			# Not Lua, don't do anything.
			return
		
		proj_file = view.window().project_file_name()
		if not proj_file:
			# No project
			return
		
		location = locations[0]
		src = view.substr(sublime.Region(0, location))
		
		match = re.search(r"""require\s*\(?\s*["']([^"]*)$""", src)
		if not match:
			return
		
		module_path = match.group(1).split(".")
		
		results = []

		for project_path in indexer.get_all_project_paths():
			proj_indexer = indexer.get_or_load_project_indexer(project_path)
			for lpath in proj_indexer.lua_paths:

				cur_path = os.path.join(project_path, lpath, *(module_path[:-1]))
				if not os.path.exists(cur_path) or not os.path.isdir(cur_path):
					continue
				print("curpath:", cur_path)
				
				_, dirs, files = next(os.walk(cur_path)) # walk splits directories and regular files for us
				
				results.extend(map(lambda x: (x+"\tsubdirectory", x), dirs))
				results.extend(map(lambda x: (x+"\tmodule", x), RequireAutocomplete.filter_lua_files(files)))
		
		return results, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS

class LuaIndexProjectCommand(sublime_plugin.WindowCommand):
	def run(self):
		indexer.generate_indices()
		self.window.status_message("generate lua project index finished.")

		indexer.write_debug_info()

class LuaIndexFileSave(sublime_plugin.EventListener):
	def on_post_save(self, view):
		file_path = view.file_name()
		if not file_path.endswith(".lua"):
			return

		proj_indexer = indexer.find_project_indexer(file_path)
		if proj_indexer is None:
			return

		proj_indexer.parse_file(file_path)
