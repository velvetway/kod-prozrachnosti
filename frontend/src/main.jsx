import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './styles.css'
import { Layout } from './components/common.jsx'
import Registry from './pages/Registry.jsx'
import NewCheck from './pages/NewCheck.jsx'
import Results from './pages/Results.jsx'
import SignalCard from './pages/SignalCard.jsx'
import Reference from './pages/Reference.jsx'
import Analogs from './pages/Analogs.jsx'
import Journal from './pages/Journal.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Registry />} />
          <Route path="/checks/new" element={<NewCheck />} />
          <Route path="/checks/:id" element={<Results />} />
          <Route path="/signals/:id" element={<SignalCard />} />
          <Route path="/reference" element={<Reference />} />
          <Route path="/analogs" element={<Analogs />} />
          <Route path="/journal" element={<Journal />} />
          <Route path="*" element={<div className="page"><h1>Страница не найдена</h1></div>} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
