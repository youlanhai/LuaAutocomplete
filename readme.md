
LuaAutocomplete
===============

[This link for old readme](readme.old.md)

在原来的LuaAutocomplete基础之上进行了改造：
+ 支持在工程路径下添加配置文件，用于设置lua源码路径，用于后续的符号解析。配置文件名为：**lua-autocomplete.py**

```python
LUA_PATHS = [
    "scripts",
]
```

+ 键入`require`之后，会从`LUA_PATHS`路径中搜索lua的模块，显示自动补全提示
+ 键入`xxx.`之后，如果xxx是require进来的模块，会根据require参数提供的路径来搜索模块。
如果找到了对应的模块，会从模块中搜索符号，用于自动补全提示。

# 一些sublime自动补全的配置
```js
{
	// 提示列表中，翻到编译之后循环到开头/结尾，而不是直接关闭提示框。
	"auto_complete_cycle": true,

	// 输入“.”、“:”的时候，显示补全提示框。
	"auto_complete_triggers":
	[
		{
			"characters": ".:",
			"selector": "source.lua"
		}
	]
}
```
