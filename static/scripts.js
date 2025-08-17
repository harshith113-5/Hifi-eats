var x = document.getElementById("loginForm");
var y = document.getElementById("registerForm");
var z = document.getElementById("btn");

function login() {
    x.style.left = "50px";
    y.style.left = "450px";
    z.style.left = "0px";
}

function register() {
    x.style.left = "-400px";
    y.style.left = "50px";
    z.style.left = "110px";
}

// document.getElementById('loginForm').addEventListener('submit', function(event) {
//     event.preventDefault();

//     const username = document.getElementById('loginUsername').value;
//     const password = document.getElementById('loginPassword').value;

//     if (username === "user" && password === "password") {
//         alert("Login successful!");
//     } else {
//         alert("Invalid username or password.");
//     }
// });

// document.getElementById('registerForm').addEventListener('submit', function(event) {
//     event.preventDefault();

//     const username = document.getElementById('registerUsername').value;
//     const password = document.getElementById('registerPassword').value;
//     const email = document.getElementById('registerEmail').value;

//     alert("Registration successful!\nUsername: " + username + "\nEmail: " + email);
// });