const puppeteer = require('puppeteer');
const express = require('express');
const cors = require('cors');
const sqlite3 = require('sqlite3').verbose();

const app = express();
app.use(cors());
app.use(express.json());

const db = new sqlite3.Database('./rates.db');

function getRandomUserAgent() {
  const userAgents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
    'Mozilla/5.0 (Linux; Android 10; Pixel 3 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Mobile Safari/537.36',
    // Добавьте больше User-Agent строк по желанию
  ];
  return userAgents[Math.floor(Math.random() * userAgents.length)];
}

db.serialize(() => {
  db.run(`
    CREATE TABLE IF NOT EXISTS rates (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      rate REAL NOT NULL,
      source TEXT NOT NULL,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);
});

// Функция для удаления старых записей
const cleanOldRates = () => {
  db.run(`
    DELETE FROM rates 
    WHERE id NOT IN (
      SELECT id FROM rates 
      ORDER BY timestamp DESC 
      LIMIT 5
    )
  `, (err) => {
    if (err) console.error('❌ Ошибка при удалении старых курсов:', err);
  });
};

const fetchData = async () => {
  let browser = null;
  
  try {
    console.log('🚀 Запуск браузера...');
    const isLinux = process.platform === 'linux';
    const executablePath = isLinux ? '/usr/bin/google-chrome' : 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

    browser = await puppeteer.launch({ 
      executablePath: executablePath,
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    const page = await browser.newPage();
    await page.setDefaultNavigationTimeout(61001);

    const randomUserAgent = getRandomUserAgent();
    await page.setUserAgent(randomUserAgent);

    console.log('📄 Переход на rapira.org...');
    await page.goto('https://rapira.org/exchange/USDT_RUB', { 
      waitUntil: 'networkidle2',
      timeout: 61001
    });

    console.log('⏳ Ожидание загрузки курса...');
    await page.waitForSelector('span.me-2', { timeout: 10000 });

    console.log('🔍 Извлечение курса...');
    const rateText = await page.evaluate(() => {
      const span = document.querySelector('span.me-2');
      return span ? span.textContent.trim() : null;
    });

    if (!rateText) {
      throw new Error('Элемент с курсом не найден');
    }

    const rate = parseFloat(rateText.replace(',', '.')); 
    if (isNaN(rate)) {
      throw new Error('Не удалось извлечь числовое значение');
    }

    await new Promise((resolve, reject) => {
      db.run(
        'INSERT INTO rates (rate, source) VALUES (?, ?)',
        [rate, 'Rapira'],
        function(err) {
          if (err) {
            console.error('❌ Ошибка записи в БД:', err);
            reject(err);
          } else {
            console.log('💾 Курс сохранён в БД');
            cleanOldRates();
            resolve();
          }
        }
      );
    });

    return rate;
  } catch (error) {
    console.error('❌ Ошибка:', error.message);
    return null;
  } finally {
    if (browser) {
      await browser.close().catch(e => console.error('Ошибка при закрытии браузера:', e));
    }
  }
};


// API для получения последнего курса
app.get('/api/rate', (req, res) => {
  db.get(
    'SELECT rate, timestamp FROM rates ORDER BY timestamp DESC LIMIT 1',
    (err, row) => {
      if (err || !row) {
        return res.status(503).json({
          success: false,
          error: 'Курс недоступен',
          rate: 92.5,
          source: 'Fallback'
        });
      }
      res.json({
        success: true,
        rate: row.rate,
        lastUpdate: row.timestamp,
        source: 'Rapira (DB)'
      });
    }
  );
});

// Запуск сервера
const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`🌐 Сервер запущен на порту ${PORT}`);
  
  // Первое получение курса
  fetchData()
    .then(rate => {
      if (rate) {
        console.log(`🔄 Первый курс получен: ${rate}`);
      } else {
        console.log('🔄 Не удалось получить первый курс');
      }
    });
  
  // Обновление каждые 60 секунд
  setInterval(fetchData, 60000);
});