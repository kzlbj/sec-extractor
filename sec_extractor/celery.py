import os
from celery import Celery

# 设置Django项目的默认设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sec_extractor.settings')

app = Celery('sec_extractor')

# 使用字符串表示，这样worker不需要序列化配置对象
app.config_from_object('django.conf:settings', namespace='CELERY')

# 从所有已注册的Django应用中加载任务模块
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}') 