import { Outlet } from 'react-router-dom'
import './App.css'

function App() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 flex flex-col">
      <main className="flex-1 flex flex-col">
        <Outlet />
      </main>
    </div>
  )
}

export default App