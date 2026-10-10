# 改标准

先读 [../standards/literature.md](../standards/literature.md)，把对应范围告诉用户。

用户仍坚持范围外的数：

1. 写入 `settings/config.json` 的 `targets`。
2. `protein_source` 或抗阻来源写成 `user_outside_literature`。
3. 向 `settings/log.jsonl` 追加一行：日期、旧值、新值、句子「超出文献范围，按用户自定义计分」。
4. 之后计分用新值。不把保存拒绝掉。

范围内的修改同样写日志，来源写成 `user_within_literature`。
