from celery import Celery

app = Celery('worker')

# Basic configuration
app.conf.broker_url = 'pyamqp://guest@rabbitmq//'
app.conf.result_backend = 'rpc://'

@app.task
def process_document():
    return "Document processed"
