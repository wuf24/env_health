# bakeup

这里存放的是 `6 未来情景分析/` 模块里 **已经退出当前主线** 的旧内容。  
它的作用不是继续提供当前结果，而是保留：

- 旧版目录结构；
- 旧日志；
- 旧缓存；
- 需要追溯但不该再留在主结果区的历史产物。

## 当前主要内容

- `results_legacy/`
  - 旧版未来情景结果结构。
- `logs_archive/`
  - 旧日志归档。
- `cache/`
  - 历史缓存或临时中间文件。

## 这些内容现在不再是主线

当前未来情景模块已经改成：

- 以 `results/` 为当前主结果目录；
- 以 `index.html` 为主页面入口；
- 以 `baseline_mode_compare/`、`lancet_ets/`、`x_driven/` 为主要结果层。

因此如果你要看当前结果，请回到上一层，优先看：

- `../README.md`
- `../index.html`
- `../results/run_metadata.json`
- `../results/lancet_ets/`
- `../results/x_driven/`
- `../results/baseline_mode_compare/`

## 什么时候才应该回来看这里

- 需要解释目录结构是怎样从旧版演进到当前扁平结构；
- 需要追溯历史图件、旧日志或旧目录命名；
- 需要确认某个文件为什么不在当前 `results/` 里了。

## 一句话记住这个目录

这里是未来情景模块的历史仓，不是当前结果入口；看当前结果，先回上一层。
