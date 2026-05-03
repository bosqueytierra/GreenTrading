// assets/config.example.js
// 
// INSTRUCCIONES:
// 1. Copia este archivo y renómbralo a config.js
// 2. Reemplaza los valores con tus credenciales reales de Supabase
// 3. Opcionalmente: agrega config.js al .gitignore para no commitear credenciales
//
// NOTA: Si usas GitHub Pages, es seguro usar la ANON KEY pública de Supabase
// siempre que hayas configurado correctamente las Row Level Security policies.

const SUPABASE_CONFIG = {
    url: 'https://tu-proyecto.supabase.co',
    anonKey: 'tu-anon-key-aqui'
};

// Exportar para uso en app.js (si usas módulos ES6)
// Si no, mantén las variables en app.js directamente
