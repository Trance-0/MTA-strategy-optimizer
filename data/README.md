# 共享数据目录

该目录预留给两个或更多模块共同使用的数据，当前没有共享数据文件。

- 通用 MTA 专用数据：[`modules/mta/data/`](../modules/mta/data/)
- AMC MTA 专用数据：[`modules/amc_mta/data/`](../modules/amc_mta/data/)
- 外部 API 参考数据：[`docs/research/amazon/research/`](../docs/research/amazon/research/)

不要为了集中存放而复制模块数据；只有出现明确的跨模块共同依赖时，才在这里建立数据集及其数据契约。

