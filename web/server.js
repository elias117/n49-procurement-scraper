const express = require('express');
const app = express();
const PORT = 3000;

app.get('/', (req, res) => {
  res.json({
    status: 'ok',
    service: 'procurement-web',
    phase: 1,
    message: 'Next.js application will be implemented in Phase 4'
  });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Web stub listening on port ${PORT}`);
});
