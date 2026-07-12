const express = require('express');
const fs = require('fs');
const path = require('path');

const app = express();
const publicDir = path.join(__dirname, 'public');
const reportPath = path.join(publicDir, 'report-data.json');

app.use(express.static(publicDir, {
  extensions: ['html'],
  maxAge: '5m'
}));

app.get('/api/report', (req, res) => {
  fs.readFile(reportPath, 'utf8', (error, raw) => {
    if (error) {
      res.status(503).json({ error: 'report-data.json is not available yet' });
      return;
    }

    try {
      res.json(JSON.parse(raw));
    } catch (parseError) {
      res.status(500).json({ error: 'report-data.json is invalid' });
    }
  });
});

app.get('*', (req, res) => {
  res.sendFile(path.join(publicDir, 'index.html'));
});

const port = process.env.PORT || 3000;
if (require.main === module) {
  app.listen(port, () => {
    console.log(`Hedge signal dashboard running on http://localhost:${port}`);
  });
}

module.exports = app;
