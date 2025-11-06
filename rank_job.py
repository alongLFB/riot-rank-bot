import time
from apscheduler.schedulers.background import BackgroundScheduler
from main_logic import process_rank_list

def job():
    print("刷新排行榜...")
    process_rank_list()
    print("刷新完成！")

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(job, 'cron', hour=3, minute=0)
    scheduler.start()

    print("Rank Job 已启动")
    while True:
        time.sleep(3600)
