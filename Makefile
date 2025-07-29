.PHONY: help dev train annotate clean status

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev:  ## Start development environment
	docker compose up --build backend streamlit db rabbitmq minio

annotate:  ## Start annotation interface only
	docker compose up --build streamlit

train-local:  ## Run training pipeline locally
	cd ai_training && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python scripts/data_pipeline.py && python scripts/model_trainer.py

train-docker:  ## Run training in Docker
	docker compose --profile training up --build ai-training

eval:  ## Evaluate trained model
	cd ai_training && python scripts/model_trainer.py --mode eval

predict:  ## Run prediction on sample
	cd ai_training && python scripts/model_trainer.py --mode predict

clean:  ## Clean up generated files
	docker compose down -v
	rm -rf data/images data/yolo data/splits
	docker system prune -f

status:  ## Show training dataset status
	@echo "=== Dataset Status ==="
	@find data/raw_pdfs -name "*.pdf" 2>/dev/null | wc -l | xargs echo "PDFs:"
	@find data/annotations -name "*.jsonl" 2>/dev/null | wc -l | xargs echo "Annotation files:"
	@if [ -d data/yolo ]; then echo "YOLO dataset: Ready"; else echo "YOLO dataset: Not created"; fi
	@if [ -f models/best_field_detector.pt ]; then echo "Model: Trained"; else echo "Model: Not trained"; fi
