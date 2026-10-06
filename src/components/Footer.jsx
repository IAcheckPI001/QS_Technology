
import styles from "../assets/css/Footer.module.css"

function Footer() {


    return (
        <div id={styles.frameFooter} className="width-100">
            <p style={{margin: "5px"}}>&copy; {new Date().getFullYear()} - QS Technology demo </p>
        </div>
    );

}

export default Footer