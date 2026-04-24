# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2026-04-24

### Added
- 统一去重服务层 (DeduplicationService)
- 事务性文件操作支持 (TransactionalFileOperation)
- AI提取结果缓存 (CacheManager)
- 异步数据库操作支持 (AsyncDatabaseOperations)
- 后台缓存写入器 - 非阻塞队列处理AI缓存写入
- 新的数据库索引优化查询性能
- 文件操作日志表 (file_operations_log)
- 错误恢复管理器 (RecoveryManager)

### Changed
- 重构版本管理为数据库为主
- 改进错误处理和异常分类
- 优化去重检查流程
- AI提取器支持缓存
- Workflow集成新的去重服务

### Fixed
- 修复文件操作与数据库不一致问题
- 修复重复邮件处理问题
- 增强系统鲁棒性

### Migration Notes
- 运行 `python migrations/add_file_operations_log.py` 创建新表和索引
- 所有去重相关操作现在是异步的
- 保持向后兼容，旧的 `deduplication_handler` 仍然可用

---

## Previous Versions
