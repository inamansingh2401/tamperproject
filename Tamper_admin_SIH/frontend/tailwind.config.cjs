module.exports = {
  content: ['./*.html', './*.js'],
  darkMode: 'class',
  theme: { extend: {
    fontFamily: { sans: ['Inter', 'sans-serif'] },
    colors: { sidebar: {
      bg: '#141824', hover: '#1e2336', active: '#2563eb', border: '#1f263b',
      text: '#94a3b8', textActive: '#ffffff'
    } }
  } },
  plugins: []
};
