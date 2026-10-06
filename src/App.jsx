

import "./i18n";
import Header from "./components/Header.jsx"
import Footer from "./components/Footer.jsx"
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";


import Home from './pages/Home';
import ScrollToTop from "./hooks/scrollToTop.jsx";
import.meta.env.VITE_API_URL;

function App(){
  return (
    <Router>
      <ScrollToTop />
      <Header/>
      <Routes>
        <Route path="/" element={<Home />} />
      </Routes>
      <Footer/>
    </Router>
  )

}

export default App