import { Outlet } from 'react-router-dom';

function App() {
  // Ce composant devient une coquille simple si besoin, mais pour l'instant
  // Outlet rendra le composant de la route correspondante.
  return <Outlet />;
}

export default App;