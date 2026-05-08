# Design Document: jamr.io MVP

## Overview

jamr.io is a real-time music matchmaking platform that connects users through shared music taste. The system uses Spotify OAuth for authentication, analyzes user listening history to generate taste profiles, and recommends rooms where users can chat and share Spotify Jam links for collaborative listening.

The architecture follows a clean separation between frontend and backend, with real-time communication handled via Socket.IO. The recommendation engine uses cosine similarity on taste vectors derived from Spotify audio features and listening patterns.

### Core Design Principles

- **Simplicity First**: Avoid overengineering; use straightforward patterns and minimal abstractions
- **Real-Time by Default**: All room activity (chat, joins, leaves) propagates instantly via WebSocket
- **Taste-Driven Discovery**: Music preference vectors drive room recommendations
- **External Playback**: No music streaming; leverage Spotify Jam links for collaborative listening
- **Stateless Backend**: Session state in cookies/database; backend services remain stateless for scalability

### Technology Stack

- **Frontend**: HTML, CSS, Vanilla JavaScript (no frameworks)
- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15+
- **Real-Time**: Socket.IO (Python and JavaScript clients)
- **ML/Recommendations**: NumPy, Pandas, scikit-learn
- **Authentication**: Spotify OAuth 2.0

## Architecture

### System Architecture

```mermaid
graph TB
    subgraph Client
        Browser[Web Browser]
        JS[Vanilla JavaScript]
        SocketClient[Socket.IO Client]
    end
    
    subgraph Backend
        FastAPI[FastAPI Server]
        SocketServer[Socket.IO Server]
        Auth[Auth Service]
        Rec[Recommendation Engine]
        DB[(PostgreSQL)]
    end
    
    subgraph External
        Spotify[Spotify API]
    end
    
    Browser --> JS
    JS --> FastAPI
    JS --> SocketClient
    SocketClient <--> SocketServer
    FastAPI --> Auth
    FastAPI --> Rec
    FastAPI --> DB
    SocketServer --> DB
    Auth --> Spotify
    Rec --> DB
```

### Component Responsibilities

**Frontend (Vanilla JavaScript)**
- Render UI pages: landing, room discovery, room chat
- Handle user interactions and form submissions
- Manage Socket.IO connection and event handlers
- Update DOM in response to real-time events
- Store minimal client state (current room, user session)

**FastAPI Backend**
- Serve static HTML/CSS/JS files
- Expose REST API for CRUD operations (users, rooms, messages)
- Handle Spotify OAuth flow (redirect, callback, token exchange)
- Validate and sanitize all inputs
- Enforce authentication and authorization
- Coordinate with recommendation engine

**Socket.IO Server**
- Manage WebSocket connections for real-time features
- Broadcast chat messages to room participants
- Notify room members of joins/leaves
- Update active user lists and room counts
- Handle connection/disconnection events

**Recommendation Engine**
- Fetch user top tracks/artists from Spotify API
- Extract audio features (danceability, energy, valence, etc.)
- Generate taste vectors (normalized feature averages)
- Calculate cosine similarity between user and room vectors
- Rank rooms by similarity score

**PostgreSQL Database**
- Store users, rooms, messages, room memberships
- Index on frequently queried fields (user_id, room_id, timestamps)
- Maintain referential integrity with foreign keys
- Store encrypted Spotify tokens

### Data Flow Examples

**User Authentication Flow**
1. User clicks "Login with Spotify" on landing page
2. Frontend redirects to `/auth/spotify`
3. Backend redirects to Spotify authorization URL
4. User authorizes on Spotify
5. Spotify redirects to `/auth/callback` with authorization code
6. Backend exchanges code for access token
7. Backend fetches user profile and top tracks/artists from Spotify
8. Backend generates taste vector and stores user in database
9. Backend sets session cookie and redirects to room discovery page

**Room Discovery Flow**
1. Frontend requests `/api/rooms` with optional filters
2. Backend queries database for rooms matching filters
3. Backend fetches user taste vector
4. Recommendation engine calculates similarity scores
5. Backend sorts rooms by score and returns top matches
6. Frontend renders room cards with recommendation badges

**Real-Time Chat Flow**
1. User types message and clicks send
2. Frontend emits `send_message` event via Socket.IO
3. Backend validates message (length, XSS sanitization)
4. Backend stores message in database
5. Backend broadcasts `new_message` event to all room members
6. All connected clients receive event and append message to chat UI

## Components and Interfaces

### Frontend Pages

**Landing Page** (`/`)
- Hero section with platform description
- "Login with Spotify" button
- Featured rooms preview (public data, no auth required)
- Active user/room count statistics

**Room Discovery Page** (`/discover`)
- Search bar for filtering by name/tags
- Genre filter checkboxes
- Room cards displaying: name, description, tags, user count
- "Highly Recommended" badge for similarity > 0.7
- "Create Room" button
- Click room card to navigate to room page

**Room Page** (`/room/:room_id`)
- Room header: name, description, tags
- Active users list (sidebar)
- Chat message area (scrollable, auto-scroll to bottom)
- Message input box (500 char limit)
- Spotify Jam link section (display active link, input to update)
- Leave room button

**Create Room Modal**
- Room name input (3-50 chars)
- Description textarea (max 300 chars)
- Genre tag multi-select
- Create button

### Backend API Endpoints

**Authentication**
- `GET /auth/spotify` - Redirect to Spotify authorization
- `GET /auth/callback` - Handle OAuth callback, exchange code for token
- `POST /auth/logout` - Invalidate session token
- `GET /auth/me` - Get current authenticated user

**Rooms**
- `GET /api/rooms` - List rooms with optional filters (query params: search, genres)
- `POST /api/rooms` - Create new room (requires auth)
- `GET /api/rooms/:room_id` - Get room details
- `POST /api/rooms/:room_id/join` - Join room (requires auth)
- `POST /api/rooms/:room_id/leave` - Leave room (requires auth)
- `PUT /api/rooms/:room_id/jam-link` - Update Spotify Jam link (requires auth, membership)

**Messages**
- `GET /api/rooms/:room_id/messages` - Get recent messages (limit 50)

**Users**
- `GET /api/users/:user_id` - Get user profile

### Socket.IO Events

**Client → Server**
- `join_room` - User joins a room (payload: `{room_id}`)
- `leave_room` - User leaves a room (payload: `{room_id}`)
- `send_message` - User sends chat message (payload: `{room_id, content}`)
- `update_jam_link` - User updates Spotify Jam link (payload: `{room_id, link}`)

**Server → Client**
- `user_joined` - Broadcast when user joins (payload: `{user_id, username, room_id}`)
- `user_left` - Broadcast when user leaves (payload: `{user_id, username, room_id}`)
- `new_message` - Broadcast new chat message (payload: `{message_id, user_id, username, content, timestamp}`)
- `jam_link_updated` - Broadcast Jam link update (payload: `{room_id, link, updated_by}`)
- `user_count_updated` - Broadcast user count change (payload: `{room_id, count}`)
- `active_users_updated` - Broadcast active users list (payload: `{room_id, users: [{user_id, username}]}`)

## Data Models

### Database Schema

**users**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    spotify_id VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    profile_image_url TEXT,
    access_token_encrypted TEXT NOT NULL,
    refresh_token_encrypted TEXT,
    token_expires_at TIMESTAMP,
    taste_vector JSONB NOT NULL,  -- Array of audio feature averages
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_spotify_id ON users(spotify_id);
```

**rooms**
```sql
CREATE TABLE rooms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    description VARCHAR(300),
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    genre_tags TEXT[] NOT NULL,  -- Array of genre strings
    taste_vector JSONB NOT NULL,  -- Generated from genre tags
    active_jam_link TEXT,
    user_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_rooms_genre_tags ON rooms USING GIN(genre_tags);
CREATE INDEX idx_rooms_created_at ON rooms(created_at DESC);
```

**messages**
```sql
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    room_id INTEGER REFERENCES rooms(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_messages_room_id_created_at ON messages(room_id, created_at DESC);
```

**room_memberships**
```sql
CREATE TABLE room_memberships (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    room_id INTEGER REFERENCES rooms(id) ON DELETE CASCADE,
    joined_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, room_id)
);

CREATE INDEX idx_room_memberships_user_id ON room_memberships(user_id);
CREATE INDEX idx_room_memberships_room_id ON room_memberships(room_id);
```

**sessions**
```sql
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sessions_token ON sessions(token);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
```

### Taste Vector Structure

Taste vectors are JSON arrays of normalized audio feature values:

```json
{
  "danceability": 0.65,
  "energy": 0.72,
  "valence": 0.58,
  "acousticness": 0.23,
  "instrumentalness": 0.05,
  "speechiness": 0.08,
  "tempo_normalized": 0.55
}
```

**User Taste Vector Generation**
1. Fetch user's top 50 tracks from Spotify API
2. Fetch audio features for each track
3. Calculate mean for each feature across all tracks
4. Normalize tempo to 0-1 range (divide by 200)
5. Store as JSONB in database

**Room Taste Vector Generation**
1. Map each genre tag to predefined feature values (genre → feature mapping table)
2. Average feature values across all selected genres
3. Store as JSONB in database

### Spotify OAuth Token Storage

Tokens are encrypted using Fernet (symmetric encryption) before storage:

```python
from cryptography.fernet import Fernet

# Generate key once, store in environment variable
encryption_key = os.getenv("ENCRYPTION_KEY")
cipher = Fernet(encryption_key)

# Encrypt before storing
encrypted_token = cipher.encrypt(access_token.encode())

# Decrypt when needed
access_token = cipher.decrypt(encrypted_token).decode()
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Token Encryption

*For any* Spotify access token stored in the database, the token must be encrypted using Fernet symmetric encryption before storage.

**Validates: Requirements 1.3, 15.1**

### Property 2: User Profile Persistence

*For any* successful Spotify authentication, the user's profile data (Spotify ID, display name, email, profile image) must be stored in the database and retrievable by user ID.

**Validates: Requirements 1.4, 1.6**

### Property 3: Spotify Data Fetching

*For any* user authentication, the platform must fetch the user's top tracks, top artists, and audio features from the Spotify API.

**Validates: Requirements 2.1, 2.2, 2.3**

### Property 4: Taste Vector Structure

*For any* generated taste vector (user or room), the vector must be a valid JSON object containing numeric values between 0 and 1 for the following keys: danceability, energy, valence, acousticness, instrumentalness, speechiness, tempo_normalized.

**Validates: Requirements 2.4, 2.5, 5.6**

### Property 5: Room Display Information

*For any* room displayed on the discovery page, the rendered HTML must contain the room's name, description, genre tags, and current user count.

**Validates: Requirements 3.2**

### Property 6: Filter Application

*For any* search or genre filter applied on the room discovery page, the displayed rooms must match the filter criteria (name/tag contains search term, or genre_tags array intersects with selected genres).

**Validates: Requirements 3.5**

### Property 7: Recommendation Display

*For any* authenticated user on the room discovery page, the page must display rooms sorted by similarity score in descending order.

**Validates: Requirements 3.6, 4.3, 4.4**

### Property 8: Cosine Similarity Calculation

*For any* user taste vector and room taste vector, the similarity score must equal the cosine similarity: (A · B) / (||A|| × ||B||), where A and B are the taste vectors.

**Validates: Requirements 4.1, 4.2**

### Property 9: High Recommendation Badge

*For any* room with a similarity score greater than 0.7, the room card must display a "Highly Recommended" badge or indicator.

**Validates: Requirements 4.5**

### Property 10: Room Name Validation

*For any* room creation attempt, if the room name length is less than 3 or greater than 50 characters, the platform must reject the creation and return a validation error.

**Validates: Requirements 5.2**

### Property 11: Room Description Validation

*For any* room creation attempt, if the description length exceeds 300 characters, the platform must reject the creation and return a validation error.

**Validates: Requirements 5.3**

### Property 12: Room Persistence

*For any* successful room creation, the room data (name, description, genre_tags, owner_id, taste_vector) must be stored in the database and retrievable by room ID.

**Validates: Requirements 5.5**

### Property 13: Room Ownership Assignment

*For any* room creation, the owner_id field must equal the user_id of the authenticated user who created the room.

**Validates: Requirements 5.7**

### Property 14: Room Join Membership

*For any* user joining a room, a room_memberships record must be created with the user_id and room_id, and the record must be retrievable from the database.

**Validates: Requirements 6.1, 6.2**

### Property 15: Join Notification Broadcast

*For any* user joining a room, all currently connected users in that room must receive a `user_joined` Socket.IO event containing the joining user's ID and username.

**Validates: Requirements 6.3**

### Property 16: User Count Increment

*For any* user joining a room, the room's user_count field must increase by exactly 1.

**Validates: Requirements 6.4**

### Property 17: Room Leave Membership

*For any* user leaving a room, the room_memberships record for that user and room must be deleted from the database.

**Validates: Requirements 6.5**

### Property 18: Leave Notification Broadcast

*For any* user leaving a room, all currently connected users in that room must receive a `user_left` Socket.IO event containing the leaving user's ID and username.

**Validates: Requirements 6.6**

### Property 19: User Count Decrement

*For any* user leaving a room, the room's user_count field must decrease by exactly 1.

**Validates: Requirements 6.7**

### Property 20: Message Broadcast

*For any* message sent by a user in a room, all currently connected users in that room must receive a `new_message` Socket.IO event containing the message content, sender username, and timestamp.

**Validates: Requirements 7.2**

### Property 21: Message Structure

*For any* chat message broadcast, the message payload must include the following fields: message_id, user_id, username, content, and timestamp.

**Validates: Requirements 7.3**

### Property 22: Message Persistence

*For any* chat message sent, the message must be stored in the database with room_id, user_id, content, and created_at fields, and must be retrievable by message ID.

**Validates: Requirements 7.4**

### Property 23: Recent Messages Loading

*For any* user joining a room, the platform must return the most recent messages for that room, limited to a maximum of 50 messages, ordered by created_at descending.

**Validates: Requirements 7.5**

### Property 24: XSS Sanitization

*For any* message content containing HTML special characters (<, >, &, ", '), the stored and broadcast content must have these characters escaped to their HTML entity equivalents.

**Validates: Requirements 7.6**

### Property 25: Message Length Validation

*For any* message submission, if the content length exceeds 500 characters, the platform must reject the message and return a validation error.

**Validates: Requirements 7.7**

### Property 26: Spotify Jam Link Validation

*For any* Spotify Jam link submission, if the link does not match the pattern `https://open.spotify.com/jam/*`, the platform must reject the submission and return a validation error.

**Validates: Requirements 8.2**

### Property 27: Jam Link Storage

*For any* valid Spotify Jam link submission, the link must be stored in the room's active_jam_link field and must be retrievable when querying the room.

**Validates: Requirements 8.3**

### Property 28: Jam Link Broadcast

*For any* valid Spotify Jam link submission, all currently connected users in that room must receive a `jam_link_updated` Socket.IO event containing the new link and the user who updated it.

**Validates: Requirements 8.4**

### Property 29: Jam Link Authorization

*For any* Spotify Jam link update attempt, if the requesting user is not a member of the room (no room_memberships record exists), the platform must reject the request with a 403 Forbidden status.

**Validates: Requirements 8.7**

### Property 30: User Count Broadcast

*For any* user joining or leaving a room, all currently connected users in that room must receive a `user_count_updated` Socket.IO event containing the updated count.

**Validates: Requirements 9.1**

### Property 31: Active Users Display

*For any* room page, the UI must display a list of currently active users, where each user in the room_memberships table for that room is rendered with their username.

**Validates: Requirements 9.2, 9.3**

### Property 32: Active Users List Update

*For any* user joining or leaving a room, the active users list must be updated to reflect the change (user added or removed from the list).

**Validates: Requirements 9.4, 9.5**

### Property 33: Activity Timestamp Update

*For any* room activity (message sent, user joined, user left, jam link updated), the room's updated_at timestamp must be set to the current time.

**Validates: Requirements 9.6**

### Property 34: Loading State Display

*For any* asynchronous operation (API request, Socket.IO event), the UI must display a loading indicator while the operation is in progress.

**Validates: Requirements 10.6**

### Property 35: Error Message Display

*For any* failed operation (validation error, API error, network error), the UI must display an error message describing the failure.

**Validates: Requirements 10.7**

### Property 36: User Data Persistence

*For any* user stored in the database, the record must contain non-null values for spotify_id, display_name, access_token_encrypted, and taste_vector fields.

**Validates: Requirements 12.1**

### Property 37: Room Data Persistence

*For any* room stored in the database, the record must contain non-null values for name, genre_tags, taste_vector, and owner_id fields.

**Validates: Requirements 12.2**

### Property 38: Message Data Persistence

*For any* message stored in the database, the record must contain non-null values for room_id, user_id, content, and created_at fields.

**Validates: Requirements 12.3**

### Property 39: Membership Data Persistence

*For any* room membership stored in the database, the record must contain non-null values for user_id, room_id, and joined_at fields.

**Validates: Requirements 12.4**

### Property 40: Referential Integrity

*For any* message, room membership, or room record, if the referenced user_id or room_id does not exist in the respective table, the database must reject the insert/update with a foreign key constraint violation.

**Validates: Requirements 12.5**

### Property 41: Session Token Generation

*For any* successful user authentication, the platform must generate a unique session token and store it in the sessions table with the user_id and an expiration timestamp 7 days in the future.

**Validates: Requirements 13.1, 13.5**

### Property 42: HTTP-Only Cookie

*For any* session token issued, the Set-Cookie header must include the HttpOnly flag to prevent JavaScript access.

**Validates: Requirements 13.2**

### Property 43: Session Token Validation

*For any* authenticated API request, if the session token is missing, invalid, or expired, the platform must reject the request with a 401 Unauthorized status.

**Validates: Requirements 13.3**

### Property 44: Session Invalidation

*For any* logout request, the platform must delete the session token from the sessions table, making it invalid for future requests.

**Validates: Requirements 13.6**

### Property 45: Spotify API Retry Logic

*For any* Spotify API request that fails with a transient error (5xx status, timeout), the platform must retry the request up to 3 times with exponential backoff (delays of 1s, 2s, 4s).

**Validates: Requirements 14.1**

### Property 46: Socket.IO Reconnection

*For any* Socket.IO connection drop, the client must automatically attempt to reconnect using the Socket.IO client's built-in reconnection logic.

**Validates: Requirements 14.4**

### Property 47: Validation Error Display

*For any* user input that fails validation (room name too short, message too long, invalid link format), the platform must return a clear error message indicating which field failed and why.

**Validates: Requirements 14.5**

### Property 48: Error Logging

*For any* error that occurs in the backend (API error, database error, validation error), the platform must log the error with a timestamp, error message, stack trace, and relevant context (user_id, request path).

**Validates: Requirements 14.6**

### Property 49: Input Sanitization

*For any* user input (message content, room name, room description), the platform must validate and sanitize the input before processing (trim whitespace, escape HTML, check length).

**Validates: Requirements 15.3**

### Property 50: Sensitive Data Exclusion

*For any* API response containing user data, the response must not include the access_token_encrypted, refresh_token_encrypted, or session token fields.

**Validates: Requirements 15.5**

### Property 51: Rate Limiting

*For any* API endpoint, if a user makes more than 100 requests per minute, the platform must reject subsequent requests with a 429 Too Many Requests status.

**Validates: Requirements 15.6**

## Error Handling

### Error Categories

**Validation Errors (4xx)**
- Invalid input format (room name too short, message too long)
- Missing required fields
- Unauthorized access (not authenticated, not room member)
- Return 400 Bad Request or 403 Forbidden with descriptive error message

**External Service Errors (Spotify API)**
- Transient errors (5xx, timeouts): Retry up to 3 times with exponential backoff
- Permanent errors (4xx): Return error to user with message "Unable to fetch Spotify data"
- Token expiration: Attempt token refresh, if refresh fails, redirect to login

**Database Errors**
- Connection failures: Return 503 Service Unavailable
- Constraint violations: Return 400 Bad Request with descriptive message
- Query timeouts: Retry once, if fails return 503

**Socket.IO Errors**
- Connection drops: Client automatically reconnects
- Message delivery failures: Log error, do not retry (messages are not critical)
- Authentication failures: Disconnect client and require re-authentication

### Error Response Format

All API errors return JSON with consistent structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Room name must be between 3 and 50 characters",
    "field": "name"
  }
}
```

### Logging Strategy

- All errors logged to stdout in JSON format for structured logging
- Include: timestamp, level (ERROR, WARN), message, stack trace, context (user_id, room_id, request_id)
- Use Python's `logging` module with custom formatter
- In production, logs ingested by log aggregation service (e.g., CloudWatch, Datadog)

## Testing Strategy

### Dual Testing Approach

The testing strategy employs both unit tests and property-based tests to ensure comprehensive coverage:

**Unit Tests**: Verify specific examples, edge cases, and error conditions
- Test specific Spotify OAuth callback scenarios
- Test database connection failures
- Test specific UI elements (landing page has login button)
- Test edge cases (empty message list, single user in room)

**Property-Based Tests**: Verify universal properties across all inputs
- Test that all room names within valid range are accepted
- Test that all messages are sanitized correctly
- Test that all taste vectors have correct structure
- Test that all similarity scores are calculated correctly

Together, unit tests catch concrete bugs while property tests verify general correctness across the input space.

### Property-Based Testing Configuration

**Library**: Hypothesis (Python) for backend tests

**Configuration**:
- Minimum 100 iterations per property test (due to randomization)
- Each property test must include a comment tag referencing the design document property
- Tag format: `# Feature: jamr-io-mvp, Property {number}: {property_text}`

**Example Property Test**:

```python
from hypothesis import given, strategies as st

# Feature: jamr-io-mvp, Property 10: Room Name Validation
@given(st.text(min_size=0, max_size=2))
def test_room_name_too_short_rejected(name):
    response = client.post("/api/rooms", json={"name": name, "description": "Test", "genre_tags": ["rock"]})
    assert response.status_code == 400
    assert "name" in response.json()["error"]["field"]

# Feature: jamr-io-mvp, Property 10: Room Name Validation
@given(st.text(min_size=51, max_size=100))
def test_room_name_too_long_rejected(name):
    response = client.post("/api/rooms", json={"name": name, "description": "Test", "genre_tags": ["rock"]})
    assert response.status_code == 400
    assert "name" in response.json()["error"]["field"]

# Feature: jamr-io-mvp, Property 10: Room Name Validation
@given(st.text(min_size=3, max_size=50))
def test_room_name_valid_range_accepted(name):
    response = client.post("/api/rooms", json={"name": name, "description": "Test", "genre_tags": ["rock"]})
    assert response.status_code in [200, 201]
```

### Test Coverage Goals

- Backend API endpoints: 90%+ line coverage
- Recommendation engine: 100% line coverage (critical business logic)
- Socket.IO event handlers: 80%+ coverage
- Frontend JavaScript: 70%+ coverage (focus on business logic, not DOM manipulation)

### Testing Tools

- **Backend**: pytest, pytest-asyncio, Hypothesis, httpx (for API testing)
- **Database**: pytest-postgresql (for test database fixtures)
- **Socket.IO**: python-socketio test client
- **Frontend**: Jest (if needed for complex JS logic)

### Test Organization

```
tests/
├── unit/
│   ├── test_auth.py
│   ├── test_rooms.py
│   ├── test_messages.py
│   └── test_recommendations.py
├── property/
│   ├── test_validation_properties.py
│   ├── test_recommendation_properties.py
│   └── test_persistence_properties.py
├── integration/
│   ├── test_oauth_flow.py
│   ├── test_room_lifecycle.py
│   └── test_chat_flow.py
└── fixtures/
    ├── database.py
    ├── spotify_mock.py
    └── socketio_client.py
```

### Continuous Integration

- Run all tests on every commit
- Fail build if coverage drops below thresholds
- Run property tests with increased iterations (1000) in CI for deeper coverage
- Generate coverage reports and upload to coverage service


## Implementation Details

### Spotify OAuth Flow

**Step-by-Step Implementation**:

1. **Login Initiation** (`GET /auth/spotify`)
   - Generate random state parameter for CSRF protection
   - Store state in session or temporary cache
   - Construct Spotify authorization URL with scopes: `user-read-email`, `user-top-read`
   - Redirect user to Spotify authorization page

2. **OAuth Callback** (`GET /auth/callback`)
   - Verify state parameter matches stored value
   - Exchange authorization code for access token via POST to Spotify token endpoint
   - Store access token (encrypted) and refresh token in database
   - Fetch user profile from Spotify API (`/v1/me`)
   - Fetch top tracks (`/v1/me/top/tracks?limit=50`)
   - Fetch top artists (`/v1/me/top/artists?limit=50`)
   - Fetch audio features for top tracks (`/v1/audio-features?ids=...`)
   - Generate taste vector from audio features
   - Create or update user record in database
   - Generate session token and set HTTP-only cookie
   - Redirect to room discovery page

3. **Token Refresh**
   - When access token expires (detected by 401 from Spotify API)
   - Use refresh token to obtain new access token
   - Update encrypted access token in database
   - Retry original request

### Recommendation Engine Implementation

**Taste Vector Generation (Users)**:

```python
def generate_user_taste_vector(audio_features: list[dict]) -> dict:
    """Generate taste vector from Spotify audio features."""
    if not audio_features:
        return default_taste_vector()
    
    features = {
        'danceability': [],
        'energy': [],
        'valence': [],
        'acousticness': [],
        'instrumentalness': [],
        'speechiness': [],
        'tempo': []
    }
    
    for track in audio_features:
        for key in features:
            if key in track:
                features[key].append(track[key])
    
    taste_vector = {}
    for key, values in features.items():
        if values:
            mean_value = sum(values) / len(values)
            if key == 'tempo':
                # Normalize tempo to 0-1 range (assume max 200 BPM)
                taste_vector['tempo_normalized'] = min(mean_value / 200, 1.0)
            else:
                taste_vector[key] = mean_value
    
    return taste_vector
```

**Taste Vector Generation (Rooms)**:

```python
# Predefined genre mappings
GENRE_VECTORS = {
    'rock': {'danceability': 0.5, 'energy': 0.8, 'valence': 0.6, 'acousticness': 0.3, 'instrumentalness': 0.4, 'speechiness': 0.05, 'tempo_normalized': 0.65},
    'pop': {'danceability': 0.7, 'energy': 0.7, 'valence': 0.7, 'acousticness': 0.2, 'instrumentalness': 0.1, 'speechiness': 0.1, 'tempo_normalized': 0.6},
    'hip-hop': {'danceability': 0.8, 'energy': 0.7, 'valence': 0.6, 'acousticness': 0.1, 'instrumentalness': 0.05, 'speechiness': 0.3, 'tempo_normalized': 0.55},
    'electronic': {'danceability': 0.8, 'energy': 0.8, 'valence': 0.6, 'acousticness': 0.05, 'instrumentalness': 0.6, 'speechiness': 0.05, 'tempo_normalized': 0.7},
    'jazz': {'danceability': 0.5, 'energy': 0.4, 'valence': 0.5, 'acousticness': 0.6, 'instrumentalness': 0.7, 'speechiness': 0.05, 'tempo_normalized': 0.5},
    'classical': {'danceability': 0.3, 'energy': 0.3, 'valence': 0.5, 'acousticness': 0.8, 'instrumentalness': 0.9, 'speechiness': 0.0, 'tempo_normalized': 0.4},
    'indie': {'danceability': 0.6, 'energy': 0.6, 'valence': 0.6, 'acousticness': 0.4, 'instrumentalness': 0.3, 'speechiness': 0.08, 'tempo_normalized': 0.55},
    'metal': {'danceability': 0.4, 'energy': 0.95, 'valence': 0.4, 'acousticness': 0.1, 'instrumentalness': 0.5, 'speechiness': 0.1, 'tempo_normalized': 0.75},
}

def generate_room_taste_vector(genre_tags: list[str]) -> dict:
    """Generate taste vector by averaging selected genre vectors."""
    if not genre_tags:
        return default_taste_vector()
    
    vectors = [GENRE_VECTORS.get(genre, default_taste_vector()) for genre in genre_tags]
    
    taste_vector = {}
    for key in vectors[0].keys():
        taste_vector[key] = sum(v[key] for v in vectors) / len(vectors)
    
    return taste_vector
```

**Cosine Similarity Calculation**:

```python
import math

def cosine_similarity(vec1: dict, vec2: dict) -> float:
    """Calculate cosine similarity between two taste vectors."""
    # Ensure both vectors have same keys
    keys = set(vec1.keys()) & set(vec2.keys())
    if not keys:
        return 0.0
    
    # Calculate dot product
    dot_product = sum(vec1[k] * vec2[k] for k in keys)
    
    # Calculate magnitudes
    magnitude1 = math.sqrt(sum(vec1[k] ** 2 for k in keys))
    magnitude2 = math.sqrt(sum(vec2[k] ** 2 for k in keys))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)
```

**Room Ranking**:

```python
def get_recommended_rooms(user_id: int, filters: dict = None) -> list[dict]:
    """Get rooms ranked by similarity to user's taste."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return []
    
    query = db.query(Room)
    
    # Apply filters
    if filters.get('search'):
        search_term = f"%{filters['search']}%"
        query = query.filter(
            (Room.name.ilike(search_term)) | 
            (Room.description.ilike(search_term))
        )
    
    if filters.get('genres'):
        query = query.filter(Room.genre_tags.overlap(filters['genres']))
    
    rooms = query.all()
    
    # Calculate similarity scores
    scored_rooms = []
    for room in rooms:
        score = cosine_similarity(user.taste_vector, room.taste_vector)
        scored_rooms.append({
            'room': room,
            'similarity_score': score,
            'highly_recommended': score > 0.7
        })
    
    # Sort by score descending
    scored_rooms.sort(key=lambda x: x['similarity_score'], reverse=True)
    
    return scored_rooms
```

### Socket.IO Event Handlers

**Server-Side Handlers**:

```python
from socketio import AsyncServer
import socketio

sio = AsyncServer(async_mode='asgi', cors_allowed_origins='*')

@sio.event
async def connect(sid, environ):
    """Handle client connection."""
    # Extract session token from cookie
    # Validate session and get user_id
    # Store mapping: sid -> user_id
    pass

@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    # Get user_id from sid
    # Remove user from all rooms they were in
    # Broadcast leave notifications
    pass

@sio.event
async def join_room(sid, data):
    """Handle user joining a room."""
    room_id = data['room_id']
    user_id = get_user_id_from_sid(sid)
    
    # Create room membership
    membership = RoomMembership(user_id=user_id, room_id=room_id)
    db.add(membership)
    
    # Increment user count
    room = db.query(Room).filter(Room.id == room_id).first()
    room.user_count += 1
    db.commit()
    
    # Join Socket.IO room
    await sio.enter_room(sid, f"room_{room_id}")
    
    # Broadcast join notification
    user = db.query(User).filter(User.id == user_id).first()
    await sio.emit('user_joined', {
        'user_id': user_id,
        'username': user.display_name,
        'room_id': room_id
    }, room=f"room_{room_id}")
    
    # Broadcast updated user count
    await sio.emit('user_count_updated', {
        'room_id': room_id,
        'count': room.user_count
    }, room=f"room_{room_id}")

@sio.event
async def send_message(sid, data):
    """Handle chat message."""
    room_id = data['room_id']
    content = data['content']
    user_id = get_user_id_from_sid(sid)
    
    # Validate message length
    if len(content) > 500:
        await sio.emit('error', {'message': 'Message too long'}, to=sid)
        return
    
    # Sanitize content
    content = sanitize_html(content)
    
    # Store message
    message = Message(room_id=room_id, user_id=user_id, content=content)
    db.add(message)
    db.commit()
    
    # Broadcast message
    user = db.query(User).filter(User.id == user_id).first()
    await sio.emit('new_message', {
        'message_id': message.id,
        'user_id': user_id,
        'username': user.display_name,
        'content': content,
        'timestamp': message.created_at.isoformat()
    }, room=f"room_{room_id}")
```

**Client-Side Handlers**:

```javascript
// Initialize Socket.IO connection
const socket = io('http://localhost:8000', {
    withCredentials: true  // Send cookies with connection
});

// Connection events
socket.on('connect', () => {
    console.log('Connected to server');
    // Join current room if on room page
    const roomId = getCurrentRoomId();
    if (roomId) {
        socket.emit('join_room', { room_id: roomId });
    }
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
});

// Room events
socket.on('user_joined', (data) => {
    addUserToActiveList(data.user_id, data.username);
    appendSystemMessage(`${data.username} joined the room`);
});

socket.on('user_left', (data) => {
    removeUserFromActiveList(data.user_id);
    appendSystemMessage(`${data.username} left the room`);
});

socket.on('user_count_updated', (data) => {
    updateUserCount(data.count);
});

// Chat events
socket.on('new_message', (data) => {
    appendMessage(data.username, data.content, data.timestamp);
    scrollChatToBottom();
});

// Jam link events
socket.on('jam_link_updated', (data) => {
    updateJamLinkDisplay(data.link);
    appendSystemMessage(`Jam link updated by ${data.updated_by}`);
});

// Send message
function sendMessage() {
    const input = document.getElementById('message-input');
    const content = input.value.trim();
    
    if (content.length === 0) return;
    if (content.length > 500) {
        showError('Message too long (max 500 characters)');
        return;
    }
    
    socket.emit('send_message', {
        room_id: getCurrentRoomId(),
        content: content
    });
    
    input.value = '';
}
```

### Security Implementation

**Input Sanitization**:

```python
import html
import re

def sanitize_html(text: str) -> str:
    """Escape HTML special characters to prevent XSS."""
    return html.escape(text)

def validate_spotify_jam_link(link: str) -> bool:
    """Validate Spotify Jam link format."""
    pattern = r'^https://open\.spotify\.com/jam/[a-zA-Z0-9]+$'
    return bool(re.match(pattern, link))

def validate_room_name(name: str) -> tuple[bool, str]:
    """Validate room name."""
    name = name.strip()
    if len(name) < 3:
        return False, "Room name must be at least 3 characters"
    if len(name) > 50:
        return False, "Room name must be at most 50 characters"
    return True, ""
```

**Token Encryption**:

```python
from cryptography.fernet import Fernet
import os

class TokenEncryption:
    def __init__(self):
        key = os.getenv('ENCRYPTION_KEY')
        if not key:
            raise ValueError("ENCRYPTION_KEY environment variable not set")
        self.cipher = Fernet(key.encode())
    
    def encrypt(self, token: str) -> str:
        """Encrypt a token."""
        return self.cipher.encrypt(token.encode()).decode()
    
    def decrypt(self, encrypted_token: str) -> str:
        """Decrypt a token."""
        return self.cipher.decrypt(encrypted_token.encode()).decode()

# Usage
encryptor = TokenEncryption()
encrypted = encryptor.encrypt(access_token)
# Store encrypted in database
```

**Rate Limiting**:

```python
from fastapi import Request, HTTPException
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
    
    def check_rate_limit(self, user_id: int):
        """Check if user has exceeded rate limit."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        
        # Remove old requests
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id]
            if req_time > cutoff
        ]
        
        # Check limit
        if len(self.requests[user_id]) >= self.max_requests:
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Add current request
        self.requests[user_id].append(now)

rate_limiter = RateLimiter()

# Use in endpoint
@app.get("/api/rooms")
async def get_rooms(request: Request, user_id: int = Depends(get_current_user)):
    rate_limiter.check_rate_limit(user_id)
    # ... rest of endpoint
```

**CORS Configuration**:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

### Frontend Implementation

**Page Structure**:

```
frontend/
├── index.html          # Landing page
├── discover.html       # Room discovery page
├── room.html           # Room chat page
├── css/
│   ├── main.css        # Global styles
│   ├── landing.css     # Landing page styles
│   ├── discover.css    # Discovery page styles
│   └── room.css        # Room page styles
└── js/
    ├── api.js          # API client functions
    ├── socket.js       # Socket.IO client setup
    ├── landing.js      # Landing page logic
    ├── discover.js     # Discovery page logic
    └── room.js         # Room page logic
```

**API Client** (`js/api.js`):

```javascript
const API_BASE = 'http://localhost:8000';

async function apiRequest(endpoint, options = {}) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        credentials: 'include',  // Send cookies
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        }
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error?.message || 'Request failed');
    }
    
    return response.json();
}

async function getRooms(filters = {}) {
    const params = new URLSearchParams(filters);
    return apiRequest(`/api/rooms?${params}`);
}

async function createRoom(roomData) {
    return apiRequest('/api/rooms', {
        method: 'POST',
        body: JSON.stringify(roomData)
    });
}

async function joinRoom(roomId) {
    return apiRequest(`/api/rooms/${roomId}/join`, {
        method: 'POST'
    });
}

async function getMessages(roomId) {
    return apiRequest(`/api/rooms/${roomId}/messages`);
}
```

**Room Discovery Page** (`js/discover.js`):

```javascript
let allRooms = [];

async function loadRooms() {
    showLoading();
    try {
        const filters = getFilters();
        allRooms = await getRooms(filters);
        renderRooms(allRooms);
    } catch (error) {
        showError(error.message);
    } finally {
        hideLoading();
    }
}

function renderRooms(rooms) {
    const container = document.getElementById('rooms-container');
    container.innerHTML = '';
    
    rooms.forEach(roomData => {
        const card = createRoomCard(roomData);
        container.appendChild(card);
    });
}

function createRoomCard(roomData) {
    const { room, similarity_score, highly_recommended } = roomData;
    
    const card = document.createElement('div');
    card.className = 'room-card';
    card.onclick = () => navigateToRoom(room.id);
    
    card.innerHTML = `
        ${highly_recommended ? '<span class="badge">Highly Recommended</span>' : ''}
        <h3>${escapeHtml(room.name)}</h3>
        <p>${escapeHtml(room.description)}</p>
        <div class="tags">
            ${room.genre_tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
        </div>
        <div class="user-count">${room.user_count} users</div>
        <div class="similarity">Match: ${(similarity_score * 100).toFixed(0)}%</div>
    `;
    
    return card;
}

function getFilters() {
    const search = document.getElementById('search-input').value;
    const selectedGenres = Array.from(
        document.querySelectorAll('.genre-filter:checked')
    ).map(cb => cb.value);
    
    return {
        search: search || undefined,
        genres: selectedGenres.length > 0 ? selectedGenres : undefined
    };
}

// Event listeners
document.getElementById('search-input').addEventListener('input', debounce(loadRooms, 300));
document.querySelectorAll('.genre-filter').forEach(cb => {
    cb.addEventListener('change', loadRooms);
});

// Initial load
loadRooms();
```

### Deployment Considerations

**Environment Variables**:

```bash
# .env file
DATABASE_URL=postgresql://user:password@localhost:5432/jamr_io
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8000/auth/callback
ENCRYPTION_KEY=your_fernet_key
SESSION_SECRET=your_session_secret
CORS_ORIGINS=http://localhost:3000
```

**Database Migrations**:

Use Alembic for database migrations:

```bash
# Initialize Alembic
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

**Running Locally**:

```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start FastAPI server
uvicorn main:app --reload --port 8000

# Serve frontend (simple HTTP server)
cd frontend
python -m http.server 3000
```

**Docker Setup** (Optional):

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: jamr_io
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://user:password@db:5432/jamr_io
    depends_on:
      - db

volumes:
  postgres_data:
```

**Production Considerations**:

- Use a production WSGI server (Gunicorn with Uvicorn workers)
- Enable HTTPS with SSL certificates (Let's Encrypt)
- Use a managed PostgreSQL service (AWS RDS, Heroku Postgres)
- Set up log aggregation (CloudWatch, Datadog, Sentry)
- Configure CDN for static assets
- Set up monitoring and alerting
- Use environment-specific configuration files
- Implement database connection pooling
- Enable database backups
- Set up CI/CD pipeline for automated deployments

