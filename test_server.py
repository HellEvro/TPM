#!/usr/bin/env python3
"""
Простой тест Flask сервера
"""

from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>Test Server Works!</h1>'

@app.route('/api/status')
def status():
    return jsonify({
        'status': 'online',
        'message': 'Test server is working'
    })

if __name__ == '__main__':
    print("🚀 Запуск тестового сервера...")
    app.run(host='0.0.0.0', port=5001, debug=True)
