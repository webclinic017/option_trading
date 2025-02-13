#!/bin/bash
echo "Starting barchart scraping..."
python3 /home/pi/Documents/python_scripts/option_trading/scheduled_jobs/scraping/barchart_scraping.py >> /home/pi/scripts/barchart_scraping.log
echo "Barchart scraping... Done"
echo "Starting s3 sync..."
/home/pi/.local/bin/aws s3 sync /home/pi/Documents/python_scripts/option_trading/data/barchart/. s3://project-option-trading/raw_data/barchart/ >> /home/pi/scripts/barchart_scraping.log
echo "s3 sync... Done"
