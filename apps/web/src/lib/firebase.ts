import { initializeApp, getApps } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyBotQBrsFeo0B81MwuoBTK1Gn4_TxbA_TE",
  authDomain: "shieldapp-40833.firebaseapp.com",
  projectId: "shieldapp-40833",
  storageBucket: "shieldapp-40833.firebasestorage.app",
  messagingSenderId: "536796060917",
  appId: "1:536796060917:web:7d29f9a0120a9da9dd79bc",
};

const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
export const auth = getAuth(app);
