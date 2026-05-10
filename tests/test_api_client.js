/**
 * Simple validation test for frontend/js/api.js
 * Verifies that all required functions are defined and exported
 */

// Mock browser globals for Node.js environment
global.window = { location: { origin: 'http://localhost:8000' } };
global.document = {
    createElement: () => ({
        textContent: '',
        innerHTML: '',
        style: {},
        remove: () => {},
        appendChild: () => {}
    }),
    body: {
        appendChild: () => {}
    }
};
global.fetch = async () => ({
    ok: true,
    json: async () => ({}),
    statusText: 'OK'
});

// Load the API client
const fs = require('fs');
const path = require('path');
const apiClientCode = fs.readFileSync(
    path.join(__dirname, '../frontend/js/api.js'),
    'utf8'
);

// Execute the code in the current context
eval(apiClientCode);

// Test that all required functions are defined
console.log('Testing API client functions...');

const requiredFunctions = [
    'apiRequest',
    'getRooms',
    'createRoom',
    'joinRoom',
    'getMessages',
    'leaveRoom',
    'updateJamLink',
    'getCurrentUser',
    'logout',
    'escapeHtml',
    'showError',
    'showLoading',
    'showEmptyState',
    'debounce'
];

let allTestsPassed = true;

for (const funcName of requiredFunctions) {
    if (typeof eval(funcName) === 'function') {
        console.log(`✓ ${funcName} is defined`);
    } else {
        console.error(`✗ ${funcName} is NOT defined`);
        allTestsPassed = false;
    }
}

// Test that API_BASE is defined
if (typeof API_BASE === 'string') {
    console.log(`✓ API_BASE is defined: ${API_BASE}`);
} else {
    console.error('✗ API_BASE is NOT defined');
    allTestsPassed = false;
}

// Test apiRequest function signature
console.log('\nTesting function signatures...');

// Test that functions return promises
const testPromise = apiRequest('/test');
if (testPromise instanceof Promise) {
    console.log('✓ apiRequest returns a Promise');
} else {
    console.error('✗ apiRequest does NOT return a Promise');
    allTestsPassed = false;
}

// Test getRooms with filters
const testGetRooms = getRooms({ search: 'test', genres: ['rock', 'jazz'] });
if (testGetRooms instanceof Promise) {
    console.log('✓ getRooms accepts filters and returns a Promise');
} else {
    console.error('✗ getRooms does NOT return a Promise');
    allTestsPassed = false;
}

// Test createRoom with data
const testCreateRoom = createRoom({ name: 'Test Room', description: 'Test', genre_tags: ['rock'] });
if (testCreateRoom instanceof Promise) {
    console.log('✓ createRoom accepts room data and returns a Promise');
} else {
    console.error('✗ createRoom does NOT return a Promise');
    allTestsPassed = false;
}

// Test joinRoom with room ID
const testJoinRoom = joinRoom(1);
if (testJoinRoom instanceof Promise) {
    console.log('✓ joinRoom accepts room ID and returns a Promise');
} else {
    console.error('✗ joinRoom does NOT return a Promise');
    allTestsPassed = false;
}

// Test getMessages with room ID
const testGetMessages = getMessages(1);
if (testGetMessages instanceof Promise) {
    console.log('✓ getMessages accepts room ID and returns a Promise');
} else {
    console.error('✗ getMessages does NOT return a Promise');
    allTestsPassed = false;
}

// Test escapeHtml
const escapedText = escapeHtml('<script>alert("xss")</script>');
if (escapedText.includes('&lt;') && escapedText.includes('&gt;')) {
    console.log('✓ escapeHtml properly escapes HTML');
} else {
    console.error('✗ escapeHtml does NOT properly escape HTML');
    allTestsPassed = false;
}

// Test debounce
let callCount = 0;
const debouncedFunc = debounce(() => callCount++, 100);
if (typeof debouncedFunc === 'function') {
    console.log('✓ debounce returns a function');
} else {
    console.error('✗ debounce does NOT return a function');
    allTestsPassed = false;
}

console.log('\n' + '='.repeat(50));
if (allTestsPassed) {
    console.log('✓ All tests passed!');
    process.exit(0);
} else {
    console.error('✗ Some tests failed!');
    process.exit(1);
}
