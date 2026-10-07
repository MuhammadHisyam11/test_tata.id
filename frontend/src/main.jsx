import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Font dibundel lokal (tanpa internet) supaya tampilan sama di semua komputer.
import '@fontsource/plus-jakarta-sans/400.css'
import '@fontsource/plus-jakarta-sans/600.css'
import '@fontsource/plus-jakarta-sans/700.css'
import './styles.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
