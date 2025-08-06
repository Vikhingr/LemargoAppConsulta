// public/firebase-messaging-sw.js
// Importa los scripts de Firebase desde CDN
importScripts('https://www.gstatic.com/firebasejs/8.10.0/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/8.10.0/firebase-messaging.js');

// Configuración de Firebase para el Service Worker.
// El 'messagingSenderId' es crucial aquí para la comunicación con FCM.
const firebaseConfig = {
  // Las siguientes claves no son estrictamente necesarias para el Service Worker en sí,
  // pero se incluyen para una inicialización completa si fuera necesario.
  "apiKey": "AIzaSyCCCW3wmQ8sGjsiehPWI65JIEUaaej9VXQ",
  "authDomain": "lemargo-app-de-consulta.firebaseapp.com",
  "projectId": "lemargo-app-de-consulta",
  "storageBucket": "lemargo-app-de-consulta.firebasestorage.app",
  "messagingSenderId": "120054139227",
  "appId": "1:120054139227:web:531983ede51253e35ef27e"
};

// Inicializa la aplicación Firebase en el Service Worker
firebase.initializeApp(firebaseConfig);

// Obtiene la instancia de mensajería
const messaging = firebase.messaging();

// Maneja los mensajes recibidos cuando la aplicación está en segundo plano (cerrada o en otra pestaña)
messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw.js] Mensaje recibido en segundo plano: ', payload);

  // Extrae el título y el cuerpo de la notificación
  const notificationTitle = payload.notification.title || 'Nueva Notificación';
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/public/icons/icon-192.png' // Asegúrate de que esta ruta a tu icono sea correcta
    // Puedes añadir más opciones aquí, como imagen, acciones, etc.
  };
  
  // Muestra la notificación al usuario
  self.registration.showNotification(notificationTitle, notificationOptions);
});
