import sys
import os
import datetime
sys.path.insert(0, os.getcwd())
from app.models.report import Report
from app.services.export_ppt import PPTXExporter
from app.services.export_pdf import PDFExporter

sample = Report(
    title='Laporan Keamanan Siber Bulanan',
    data_type='firewall',
    input_file_name='sample_firewall.csv',
    period_start=datetime.date(2026, 7, 1),
    period_end=datetime.date(2026, 7, 31),
    language='Indonesian',
    header_title='PT PETROKIMIA GRESIK',
    header_subtitle='Laporan Analitik Keamanan Siber',
    ai_summary={
        'executive_summary': 'Ringkasan eksekutif singkat.',
        'trend_analysis': 'Tren meningkat pada paruh kedua.',
        'severity_analysis': 'Sebagian besar insiden berada pada tingkat medium.',
        'risk_assessment': 'Risiko terkendali dengan mitigasi yang tepat.',
        'recommendations': [{'title': 'Perkuat firewall', 'detail': 'Level akses harus ditinjau.'}],
        'conclusion': 'Kesimpulan akhir laporan ini.'
    },
    chart_data={
        'charts': [
            {
                'kind': 'trend',
                'layout': {'title': {'text': 'Trend Serangan'}},
                'data': []
            }
        ]
    },
    parsed_data=[
        {'timestamp': '2026-07-01T01:00:00Z', 'severity': 'medium', 'source_ip': '10.0.0.1', 'destination_ip': '10.0.0.2'}
    ]
)
print('PPT', len(PPTXExporter.generate_ppt_report(sample)))
print('PDF', len(PDFExporter.generate_pdf_report(sample)))
