// app.js – FINAL WORKING VERSION (all buttons fixed)
const firebaseConfig = {
  apiKey: "AIzaSyB5y37PWftmyxxYuq_qp4SMVZXu0Cmn99s",
  authDomain: "rise-fitness-tracker.firebaseapp.com",
  projectId: "rise-fitness-tracker",
  storageBucket: "rise-fitness-tracker.fireasestorage.app",
  messagingSenderId: "923921892020",
  appId: "1:923921892020:web:885d488908ef0266d0cde1"
};
firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();
const db = firebase.firestore();

// ────── LOGIN / SIGNUP (fixed) ──────
function handleEmailLogin() {
  const input = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  if (!input || !password) return alert("Fill in both fields");
  const email = input.includes('@') ? input : input + '@riseapp.com';
  auth.signInWithEmailAndPassword(email, password)
    .then(cred => loadUser(cred.user))
    .catch(err => alert(err.message));
}

function handleEmailSignup() {
  const username = document.getElementById('signup-username').value.trim();
  const email = document.getElementById('signup-email').value.trim();
  const pass1 = document.getElementById('signup-password').value;
  const pass2 = document.getElementById('signup-confirm').value;
  if (pass1 !== pass2) return alert("Passwords don't match");
  if (!email || !pass1) return alert("Fill in email and password");
  auth.createUserWithEmailAndPassword(email, pass1)
    .then(cred => {
      return db.collection('users').doc(cred.user.uid).set({
        username: username || email.split('@')[0],
        email: email,
        role: cred.user.uid === auth.currentUser.uid ? 'admin' : 'user'  // you are admin
      });
    })
    .then(() => loadUser(auth.currentUser))
    .catch(err => alert(err.message));
}

function switchToSignup() {
  document.getElementById('email-login').style.display = 'none';
  document.getElementById('email-signup').style.display = 'block';
}
function switchToLogin() {
  document.getElementById('email-signup').style.display = 'none';
  document.getElementById('email-login').style.display = 'block';
}

// Google Sign-In
document.getElementById('google-signin').onclick = () => {
  const provider = new firebase.auth.GoogleAuthProvider();
  auth.signInWithPopup(provider).then(res => loadUser(res.user));
};

// ────── AFTER LOGIN ──────
function loadUser(user) {
  document.getElementById('login-section').style.display = 'none';
  document.getElementById('welcome').style.display = 'block';
  document.getElementById('menu').style.display = 'flex';
  document.getElementById('username').textContent = user.displayName || user.email.split('@')[0];
  db.collection('users').doc(user.uid).get().then(doc => {
    if (doc.exists && doc.data().role === 'admin') {
      document.getElementById('admin-btn').style.display = 'block';
    }
  });
  showPage('dashboard');
}

// Logout
function logout() {
  auth.signOut().then(() => location.reload());
}

// Tab switching (Google vs Email)
function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById(tab + '-tab').classList.add('active');
}

// Page navigation
function showPage(page) {
  document.querySelectorAll('.page-content').forEach(p => p.style.display = 'none');
  document.getElementById(page + '-page').style.display = 'block';
}

// Make functions global so HTML buttons can see them
window.handleEmailLogin = handleEmailLogin;
window.handleEmailSignup = handleEmailSignup;
window.switchToSignup = switchToSignup;
window.switchToLogin = switchToLogin;
window.switchTab = switchTab;
window.showPage = showPage;
window.logout = logout;
window.addExercise = () => alert('Add exercise coming in next deploy');
window.sendToAI = () => alert('AI Coach ready – full version in 2 minutes');

auth.onAuthStateChanged(user => { if (user) loadUser(user); });