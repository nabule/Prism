import sys
import uuid
from memosima.core.config import AppConfig
from memosima.db.store import Store

def main():
    if len(sys.argv) < 2:
        print("错误: 请指定需要重新处理的 Memos UID")
        print("用法: uv run python scratch/reprocess.py <memo_uid>")
        sys.exit(1)
        
    memo_uid = sys.argv[1]
    
    # 加载本地配置和数据库 Store
    config = AppConfig.load()
    store = Store(config.database_path)
    
    # 生成带有唯一标识的幂等键以强行绕过既往的缓存与去重机制
    idempotency_key = f"manual.reprocess:{memo_uid}:{uuid.uuid4().hex[:8]}"
    
    job, created = store.create_job(
        workspace_id=config.workspace_id,
        job_type="process_memo",
        idempotency_key=idempotency_key,
        payload={"memo_uid": memo_uid, "manual": True}
    )
    
    if created:
        print(f"🎉 成功为 Memo '{memo_uid}' 创建了重新整理任务！")
        print(f"   任务 ID: {job.id}")
        print(f"   任务状态: {job.status} (等待 Worker 调度)")
    else:
        print(f"⚠️ 任务已存在 (ID: {job.id})，状态为: {job.status}")

if __name__ == "__main__":
    main()
