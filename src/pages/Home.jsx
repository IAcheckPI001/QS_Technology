
import Chat from "./Chat.jsx";
import ChatbotWidget from "../components/ChatbotWidget.jsx";
import styles from "../assets/css/Home.module.css"

function Home () {
    return (
        <div className="container">
            <section id = {styles.section0} className="flex jc-space-around width-100">
                <Chat />
            </section>
            <ChatbotWidget />
        </div>
    );
}

export default Home
