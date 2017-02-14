
LuaAutocomplete
===============

[This link for old readme](readme.old.md)

在原来的LuaAutocomplete基础之上进行了改造：
+ 支持在sublime工程文件中添加lua路径，用于后续的符号解析。
```json
{
    "folders":
    [
        {
            "lua_paths" : [
                "your/lua/path/relative/to/project/root/path"
            ]
        }
    ]
}
```
+ 键入`require`之后，会从`lua_paths`搜索lua的模块，显示自动补全提示
+ 键入`xxx.`之后，如果xxx是require进来的模块，会根据require参数提供的路径来搜索模块。
如果找到了对应的模块，会从模块中搜索符号，用于自动补全提示。

# 一些自动补全的配置
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
