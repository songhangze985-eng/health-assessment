# 认库

每个绝对路径是一个人。换路径就是另一个人，不能读上一个库。

1. 若本仓库没有 `.memory-path`，问用户要记忆库的绝对路径。不要猜目录。
2. 把这一行写入 `.memory-path`。这个文件已在 `.gitignore`。
3. 打开该路径的 `settings/config.json`。没有代号时，问一个代号，写入 `codename`。同一路径以后不再问代号。
4. 没有 `settings/config.json` 时，先走建档工作流。
5. 用户说可以写入之后，只追加新文件。回顾旧会话时只读，不改旧 JSON。

## 库内布局

- `settings/config.json`：代号、档案、当前目标、目标来源
- `settings/log.jsonl`：每次改标准追加一行
- `sessions/YYYY-MM-DD.json`：一天一条。同一天再次打卡时追加 `sessions/YYYY-MM-DD-HHMMSS.json`，不覆盖第一条
- `inbox/`：原文副本
- `analyses/`：脚本输出的报告副本

## 交给计分脚本的档案

`profile` 必须含 `height_cm`、`weight_kg`、`age`、`sex`、`training_years`、`injury`。目标放在 `profile.targets`。
