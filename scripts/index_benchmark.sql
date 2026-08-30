DROP TABLE IF EXISTS task_index_benchmark;

CREATE TABLE task_index_benchmark (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    done BOOLEAN NOT NULL
);

INSERT INTO task_index_benchmark (title, done)
SELECT
    'Benchmark task ' || n,
    (n % 100 = 0)
FROM generate_series(1, 100000) AS n;

ANALYZE task_index_benchmark;

\echo
\echo ==================================================
\echo BEFORE INDEX
\echo ==================================================

EXPLAIN ANALYZE
SELECT id, title, done
FROM task_index_benchmark
WHERE done = TRUE;

CREATE INDEX idx_task_index_benchmark_done
ON task_index_benchmark(done);

ANALYZE task_index_benchmark;

\echo
\echo ==================================================
\echo AFTER INDEX
\echo ==================================================

EXPLAIN ANALYZE
SELECT id, title, done
FROM task_index_benchmark
WHERE done = TRUE;

DROP TABLE task_index_benchmark;
