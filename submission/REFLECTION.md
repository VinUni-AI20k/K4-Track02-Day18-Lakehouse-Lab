# Reflection

## Anti-pattern: Small files

The lakehouse anti-pattern most relevant to me is the small-file problem in LLM observability data. Frequent writes create many tiny files, increasing metadata overhead and slowing query planning and execution.

I would prevent this by batching records before writing, choosing partitions carefully, and scheduling compaction when file counts or average file sizes cross defined thresholds. For queries filtered by tenant or model, clustering or Z-order can improve file pruning.

Monitoring should track file count, average file size, planning time, and skipped-file ratios. Total storage size alone is not enough to identify this problem.
