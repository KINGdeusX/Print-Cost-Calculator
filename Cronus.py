import sys
import os
import json
from datetime import datetime
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt


CONFIG_FILE = "pricing_config.json"


class PricingCalculator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Printing Pricing Calculator")
        self.setGeometry(200, 200, 480, 600)
        self.load_config()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Customer Name
        self.name_label = QLabel("Customer / Project Name:")
        self.name_input = QLineEdit()

        # Duration inputs
        duration_layout = QHBoxLayout()
        self.day_label = QLabel("Days:")
        self.day_input = QLineEdit()
        self.day_input.setFixedWidth(60)

        self.hour_label = QLabel("Hours:")
        self.hour_input = QLineEdit()
        self.hour_input.setFixedWidth(60)

        self.min_label = QLabel("Minutes:")
        self.min_input = QLineEdit()
        self.min_input.setFixedWidth(60)

        duration_layout.addWidget(self.day_label)
        duration_layout.addWidget(self.day_input)
        duration_layout.addWidget(self.hour_label)
        duration_layout.addWidget(self.hour_input)
        duration_layout.addWidget(self.min_label)
        duration_layout.addWidget(self.min_input)

        # Filament Used
        filament_layout = QHBoxLayout()
        self.filament_label = QLabel("Filament Used (grams):")
        self.filament_input = QLineEdit()
        filament_layout.addWidget(self.filament_label)
        filament_layout.addWidget(self.filament_input)

        # Labor Cost
        labor_layout = QHBoxLayout()
        self.labor_label = QLabel("Labor Cost (₱):")
        self.labor_input = QLineEdit()
        labor_layout.addWidget(self.labor_label)
        labor_layout.addWidget(self.labor_input)

        # Configurable saved fields
        self.filament_cost_label = QLabel("Filament Cost (₱/kg):")
        self.filament_cost_input = QLineEdit(str(self.config.get("filament_cost", 800)))

        self.packaging_label = QLabel("Packaging Cost (₱):")
        self.packaging_input = QLineEdit(str(self.config.get("packaging", 20)))

        self.rate_label = QLabel("Electricity Rate (₱/kWh):")
        self.rate_input = QLineEdit(str(self.config.get("rate", 12)))

        self.power_label = QLabel("Printer Power (Watts):")
        self.power_input = QLineEdit(str(self.config.get("power", 120)))

        # Profit margin slider
        self.margin_label = QLabel(f"Profit Margin: {self.config.get('margin', 50)}%")
        self.margin_slider = QSlider(Qt.Horizontal)
        self.margin_slider.setRange(0, 100)
        self.margin_slider.setValue(self.config.get("margin", 50))
        self.margin_slider.valueChanged.connect(self.update_margin_label)

        # Buttons
        self.calc_button = QPushButton("Calculate Price")
        self.calc_button.clicked.connect(self.calculate_price)

        self.save_button = QPushButton("Save to Excel (.xlsx)")
        self.save_button.clicked.connect(self.save_to_excel)

        # Output label
        self.output_label = QLabel("Result will appear here.")
        self.output_label.setStyleSheet("font-weight: bold; margin-top: 10px;")

        # Add widgets to layout
        layout.addWidget(self.name_label)
        layout.addWidget(self.name_input)
        layout.addLayout(duration_layout)
        layout.addLayout(filament_layout)
        layout.addLayout(labor_layout)
        for widget in [
            self.filament_cost_label, self.filament_cost_input,
            self.packaging_label, self.packaging_input,
            self.rate_label, self.rate_input,
            self.power_label, self.power_input,
            self.margin_label, self.margin_slider,
            self.calc_button, self.output_label, self.save_button
        ]:
            layout.addWidget(widget)

        self.setLayout(layout)

    def update_margin_label(self):
        value = self.margin_slider.value()
        self.margin_label.setText(f"Profit Margin: {value}%")
        self.config["margin"] = value
        self.save_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                self.config = json.load(f)
        else:
            self.config = {}

    def save_config(self):
        # Save persistent values
        self.config["filament_cost"] = float(self.filament_cost_input.text() or 0)
        self.config["packaging"] = float(self.packaging_input.text() or 0)
        self.config["rate"] = float(self.rate_input.text() or 0)
        self.config["power"] = float(self.power_input.text() or 0)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f)

    def calculate_price(self):
        try:
            days = float(self.day_input.text() or 0)
            hours = float(self.hour_input.text() or 0)
            minutes = float(self.min_input.text() or 0)
            total_hours = (days * 24) + hours + (minutes / 60)

            filament_grams = float(self.filament_input.text())
            filament_cost_per_kg = float(self.filament_cost_input.text())
            labor = float(self.labor_input.text())
            packaging = float(self.packaging_input.text())
            rate = float(self.rate_input.text())
            power_watts = float(self.power_input.text())
            margin = self.margin_slider.value() / 100

            # Save config values persistently
            self.save_config()

            # Computations
            electricity_cost = (power_watts / 1000) * total_hours * rate
            filament_cost = (filament_grams / 1000) * filament_cost_per_kg
            total_cost = electricity_cost + filament_cost + labor + packaging
            suggested_price = round((total_cost * (1 + margin)) / 5) * 5

            result = (
                f"--- COST BREAKDOWN ---\n"
                f"Electricity: ₱{electricity_cost:.2f}\n"
                f"Filament: ₱{filament_cost:.2f}\n"
                f"Labor: ₱{labor:.2f}\n"
                f"Packaging: ₱{packaging:.2f}\n\n"
                f"Total Cost: ₱{total_cost:.2f}\n"
                f"Suggested Price: ₱{suggested_price:.2f}"
            )

            self.output_label.setText(result)
            self.last_calc = {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "name": self.name_input.text(),
                "duration": f"{int(days)}d {int(hours)}h {int(minutes)}m",
                "filament_used": filament_grams,
                "electricity_cost": electricity_cost,
                "filament_cost": filament_cost,
                "labor_cost": labor,
                "packaging_cost": packaging,
                "total_cost": total_cost,
                "margin": self.margin_slider.value(),
                "suggested_price": suggested_price,
            }

        except ValueError:
            QMessageBox.warning(self, "Input Error", "Please fill out all numeric fields properly.")

    def save_to_excel(self):
        if not hasattr(self, "last_calc"):
            QMessageBox.warning(self, "No Data", "Please calculate a price before saving.")
            return

        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Quote", "", "Excel Files (*.xlsx)", options=options)
        if not file_path:
            return

        new_data = pd.DataFrame([self.last_calc])
        if os.path.exists(file_path):
            try:
                existing = pd.read_excel(file_path)
                df = pd.concat([existing, new_data], ignore_index=True)
            except Exception:
                df = new_data
        else:
            df = new_data

        df.to_excel(file_path, index=False)
        QMessageBox.information(self, "Saved", f"Quote saved to:\n{file_path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PricingCalculator()
    window.show()
    sys.exit(app.exec_())
