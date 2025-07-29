#!/usr/bin/env python3
"""
Model Training for Underground Utilities Field Detection
Uses YOLOv8 for detecting and localizing table fields in civil engineering PDFs.
"""

import logging
import yaml
from pathlib import Path
from ultralytics import YOLO
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelTrainer:
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.work_dir = Path(self.config['dataset']['work_dir'])
        self.model_dir = Path(self.config['output']['model_dir'])
        self.model_dir.mkdir(exist_ok=True)

    def train_model(self):
        """Train YOLOv8 model for field detection."""
        model_config = self.config['model']
        dataset_yaml = self.work_dir / "yolo" / "dataset.yaml"
        
        if not dataset_yaml.exists():
            logger.error(f"Dataset configuration not found: {dataset_yaml}")
            logger.error("Please run data_pipeline.py first")
            return
        
        # Initialize model
        model = YOLO(f"{model_config['architecture']}.pt")
        
        # Training parameters
        train_params = {
            'data': str(dataset_yaml),
            'epochs': model_config['epochs'],
            'imgsz': model_config['input_size'],
            'batch': model_config['batch_size'],
            'lr0': model_config['learning_rate'],
            'patience': model_config['patience'],
            'project': str(self.work_dir / "yolo" / "runs"),
            'name': 'field_detection',
            'save': True,
            'save_period': 10,
            'cache': True,
            'device': 'auto',  # Use GPU if available
        }
        
        logger.info("Starting Underground Utilities field detection training...")
        logger.info(f"Training parameters: {train_params}")
        
        # Train the model
        results = model.train(**train_params)
        
        # Save the best model
        best_model_path = self.model_dir / "best_field_detector.pt"
        model.save(str(best_model_path))
        
        logger.info(f"Training completed! Best model saved to: {best_model_path}")
        
        # Export model in different formats
        export_formats = self.config['output']['export_formats']
        for fmt in export_formats:
            try:
                exported_path = model.export(format=fmt)
                logger.info(f"Model exported to {fmt}: {exported_path}")
            except Exception as e:
                logger.warning(f"Failed to export to {fmt}: {e}")
        
        return results

    def evaluate_model(self, model_path: str = None):
        """Evaluate trained model on test set."""
        if model_path is None:
            model_path = self.model_dir / "best_field_detector.pt"
        
        if not Path(model_path).exists():
            logger.error(f"Model not found: {model_path}")
            return
        
        model = YOLO(str(model_path))
        dataset_yaml = self.work_dir / "yolo" / "dataset.yaml"
        
        logger.info("Evaluating model on test set...")
        
        # Run evaluation
        results = model.val(
            data=str(dataset_yaml),
            split='test',
            save_json=True,
            save_hybrid=True,
            project=str(self.work_dir / "yolo" / "runs"),
            name='evaluation'
        )
        
        logger.info("Model evaluation completed!")
        logger.info(f"mAP50: {results.box.map50:.4f}")
        logger.info(f"mAP50-95: {results.box.map:.4f}")
        
        return results

    def predict_sample(self, model_path: str = None, image_path: str = None):
        """Run prediction on a sample image."""
        if model_path is None:
            model_path = self.model_dir / "best_field_detector.pt"
        
        if not Path(model_path).exists():
            logger.error(f"Model not found: {model_path}")
            return
        
        model = YOLO(str(model_path))
        
        if image_path is None:
            # Use a sample from test set
            test_images = list((self.work_dir / "yolo" / "images" / "test").glob("*.png"))
            if test_images:
                image_path = test_images[0]
            else:
                logger.error("No test images found")
                return
        
        logger.info(f"Running prediction on: {image_path}")
        
        # Run prediction
        results = model.predict(
            source=str(image_path),
            save=True,
            project=str(self.work_dir / "yolo" / "runs"),
            name='prediction'
        )
        
        logger.info("Prediction completed! Check the runs/prediction folder for results.")
        return results

def main():
    parser = argparse.ArgumentParser(description="Underground Utilities Model Trainer")
    parser.add_argument("--config", default="configs/training_config.yaml",
                       help="Path to training configuration file")
    parser.add_argument("--mode", choices=['train', 'eval', 'predict', 'all'], default='train',
                       help="Training mode")
    parser.add_argument("--model", help="Path to model for evaluation/prediction")
    parser.add_argument("--image", help="Path to image for prediction")
    
    args = parser.parse_args()
    
    trainer = ModelTrainer(args.config)
    
    if args.mode in ['train', 'all']:
        trainer.train_model()
    
    if args.mode in ['eval', 'all']:
        trainer.evaluate_model(args.model)
    
    if args.mode in ['predict']:
        trainer.predict_sample(args.model, args.image)

if __name__ == "__main__":
    main()
