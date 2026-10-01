from pathlib import Path
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PIL import Image

root = Path(__file__).resolve().parent.parent
image = QImage(256, 256, QImage.Format.Format_ARGB32)
image.fill(Qt.GlobalColor.transparent)
p = QPainter(image)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
p.setPen(Qt.PenStyle.NoPen)
p.setBrush(QColor('#fff0b5'))
p.drawEllipse(QRectF(8, 8, 240, 240))
p.setBrush(Qt.BrushStyle.NoBrush)
p.setPen(QPen(QColor('#514b41'), 11, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
p.drawRoundedRect(QRectF(105, 65, 46, 88), 23, 23)
arc = QPainterPath()
arc.moveTo(82, 119)
arc.cubicTo(82, 198, 174, 198, 174, 119)
p.drawPath(arc)
p.drawLine(QPointF(128, 183), QPointF(128, 210))
p.drawLine(QPointF(108, 210), QPointF(148, 210))
p.end()
png = root / 'assets' / 'app-icon.png'
image.save(str(png))
Image.open(png).save(root / 'assets' / 'app-icon.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
