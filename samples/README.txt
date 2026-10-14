Drop 3 to 6 real river photos here (plastic, foam, waste, hyacinth, the riverbank).

bus.jpg is a bundled test photo (people and a bus) used to show that unrelated
COCO classes are filtered out — it should produce no river detections.

Then run:
    python -m backend.yolo_detector --source samples --conf 0.35

The detector draws boxes and streams each detection to the live dashboard.

For real plastic detection, fine-tune YOLOv8 on the TACO dataset (or your Noyyal photos)
and pass the weights with:  --model best.pt
