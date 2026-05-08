# Implementation Plan: jamr.io MVP

## Overview

This implementation plan breaks down the jamr.io MVP into discrete, actionable coding tasks. The platform is a real-time music matchmaking system built with FastAPI (Python), PostgreSQL, Socket.IO, and vanilla JavaScript. Tasks are ordered to build incrementally, with testing integrated throughout to catch errors early.

## Tasks

- [x] 1. Project setup and infrastructure
  - [x] 1.1 Initialize Python project structure and dependencies
    - Create project directory structure (backend/, frontend/, tests/)
    - Create requirements.txt with FastAPI, SQLAlchemy, python-socketio, psycopg2, cryptography, hypothesis, pytest
    - Create .env.example file with required environment variables
    - Create .gitignore for Python and Node artifacts
    - _Requirements: 12.6, 15.2_

  - [x] 1.2 Set up database configuration and connection
    - Create database.py with SQLAlchemy engine and session management
    - Implement connection pooling configuration
    - Create Alembic configuration for migrations
    - _Requirements: 12.5, 12.6_

  - [x] 1.3 Create database schema and models
    - Define SQLAlchemy models for users, rooms, messages, room_memberships, sessions tables
    - Add indexes on frequently queried fields (user_id, room_id, timestamps)
    - Create initial Alembic migration script
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

  - [x] 1.4 Write property tests for database models
    - **Property 36: User Data Persistence** - Validates: Requirements 12.1
    - **Property 37: Room Data Persistence** - Validates: Requirements 12.2
    - **Property 38: Message Data Persistence** - Validates: Requirements 12.3
    - **Property 39: Membership Data Persistence** - Validates: Requirements 12.4
    - **Property 40: Referential Integrity** - Validates: Requirements 12.5

  - [x] 1.5 Set up FastAPI application structure
    - Create main.py with FastAPI app initialization
    - Configure CORS middleware with allowed origins
    - Set up static file serving for frontend
    - Add health check endpoint
    - _Requirements: 15.4_

- [-] 2. Security and encryption infrastructure
  - [x] 2.1 Implement token encryption service
    - Create encryption.py with Fernet-based TokenEncryption class
    - Implement encrypt() and decrypt() methods
    - Load encryption key from environment variable
    - _Requirements: 1.3, 15.1_

  - [x] 2.2 Write property test for token encryption
    - **Property 1: Token Encryption** - Validates: Requirements 1.3, 15.1

  - [x] 2.3 Implement input sanitization utilities
    - Create validators.py with sanitize_html() function
    - Implement validate_spotify_jam_link() function
    - Implement validate_room_name() and validate_room_description() functions
    - Implement validate_message_content() function
    - _Requirements: 7.6, 7.7, 8.2, 15.3_

  - [x] 2.4 Write property tests for input validation
    - **Property 10: Room Name Validation** - Validates: Requirements 5.2
    - **Property 11: Room Description Validation** - Validates: Requirements 5.3
    - **Property 24: XSS Sanitization** - Validates: Requirements 7.6
    - **Property 25: Message Length Validation** - Validates: Requirements 7.7
    - **Property 26: Spotify Jam Link Validation** - Validates: Requirements 8.2

  - [x] 2.4 Implement rate limiting middleware
    - Create rate_limiter.py with RateLimiter class
    - Implement check_rate_limit() method with sliding window algorithm
    - Add rate limiting dependency to FastAPI routes
    - _Requirements: 15.6_

  - [x] 2.5 Write property test for rate limiting
    - **Property 51: Rate Limiting** - Validates: Requirements 15.6

- [ ] 3. Spotify OAuth authentication flow
  - [ ] 3.1 Implement Spotify OAuth redirect endpoint
    - Create auth.py with /auth/spotify endpoint
    - Generate and store CSRF state parameter
    - Construct Spotify authorization URL with required scopes
    - Redirect user to Spotify authorization page
    - _Requirements: 1.1, 1.2_

  - [ ] 3.2 Implement OAuth callback handler
    - Create /auth/callback endpoint
    - Verify CSRF state parameter
    - Exchange authorization code for access token
    - Store encrypted access and refresh tokens in database
    - _Requirements: 1.3, 1.4_

  - [ ] 3.3 Write property test for OAuth token storage
    - **Property 1: Token Encryption** - Validates: Requirements 1.3, 15.1
    - **Property 2: User Profile Persistence** - Validates: Requirements 1.4, 1.6

  - [ ] 3.4 Fetch and store user profile data
    - Call Spotify /v1/me endpoint to get user profile
    - Extract spotify_id, display_name, email, profile_image_url
    - Create or update user record in database
    - _Requirements: 1.4, 1.6_

  - [ ] 3.5 Implement session management
    - Generate unique session token on successful authentication
    - Store session in sessions table with 7-day expiration
    - Set HTTP-only cookie with session token
    - Redirect to room discovery page
    - _Requirements: 13.1, 13.2, 13.5_

  - [ ] 3.6 Write property tests for session management
    - **Property 41: Session Token Generation** - Validates: Requirements 13.1, 13.5
    - **Property 42: HTTP-Only Cookie** - Validates: Requirements 13.2
    - **Property 43: Session Token Validation** - Validates: Requirements 13.3

  - [ ] 3.7 Implement authentication middleware
    - Create get_current_user() dependency function
    - Validate session token from cookie
    - Check token expiration
    - Return 401 if invalid or expired
    - _Requirements: 13.3, 13.4_

  - [ ] 3.8 Implement logout endpoint
    - Create /auth/logout endpoint
    - Delete session token from database
    - Clear session cookie
    - _Requirements: 13.6_

  - [ ] 3.9 Write property test for session invalidation
    - **Property 44: Session Invalidation** - Validates: Requirements 13.6

  - [ ] 3.10 Implement token refresh logic
    - Create refresh_spotify_token() function
    - Detect 401 errors from Spotify API
    - Use refresh token to obtain new access token
    - Update encrypted token in database
    - _Requirements: 14.1_

- [ ] 4. Checkpoint - Ensure authentication flow works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Music taste analysis and recommendation engine
  - [ ] 5.1 Fetch user listening data from Spotify
    - Create spotify_client.py with SpotifyClient class
    - Implement get_user_top_tracks() method (limit 50)
    - Implement get_user_top_artists() method (limit 50)
    - Implement get_audio_features() method for track IDs
    - Add retry logic with exponential backoff for transient errors
    - _Requirements: 2.1, 2.2, 2.3, 14.1_

  - [ ] 5.2 Write property test for Spotify API retry logic
    - **Property 45: Spotify API Retry Logic** - Validates: Requirements 14.1

  - [ ] 5.3 Implement user taste vector generation
    - Create recommendation_engine.py with generate_user_taste_vector() function
    - Calculate mean values for danceability, energy, valence, acousticness, instrumentalness, speechiness
    - Normalize tempo to 0-1 range (divide by 200)
    - Return taste vector as dictionary
    - _Requirements: 2.4, 2.5_

  - [ ] 5.4 Write property tests for taste vector structure
    - **Property 3: Spotify Data Fetching** - Validates: Requirements 2.1, 2.2, 2.3
    - **Property 4: Taste Vector Structure** - Validates: Requirements 2.4, 2.5, 5.6

  - [ ] 5.5 Implement room taste vector generation
    - Define GENRE_VECTORS mapping with predefined feature values
    - Implement generate_room_taste_vector() function
    - Average feature values across selected genre tags
    - _Requirements: 5.6_

  - [ ] 5.6 Implement cosine similarity calculation
    - Create cosine_similarity() function
    - Calculate dot product of two taste vectors
    - Calculate magnitudes of both vectors
    - Return similarity score (0-1 range)
    - _Requirements: 4.1, 4.2_

  - [ ] 5.7 Write property test for cosine similarity
    - **Property 8: Cosine Similarity Calculation** - Validates: Requirements 4.1, 4.2

  - [ ] 5.8 Implement room recommendation ranking
    - Create get_recommended_rooms() function
    - Fetch user taste vector from database
    - Calculate similarity score for each room
    - Sort rooms by similarity score descending
    - Mark rooms with score > 0.7 as highly recommended
    - _Requirements: 4.3, 4.4, 4.5_

  - [ ] 5.9 Write property tests for recommendations
    - **Property 7: Recommendation Display** - Validates: Requirements 3.6, 4.3, 4.4
    - **Property 9: High Recommendation Badge** - Validates: Requirements 4.5

- [ ] 6. Room management API endpoints
  - [ ] 6.1 Implement GET /api/rooms endpoint
    - Accept optional query parameters: search, genres
    - Filter rooms by name/description containing search term
    - Filter rooms by genre_tags overlapping with selected genres
    - Call get_recommended_rooms() to rank by similarity
    - Return list of rooms with similarity scores
    - _Requirements: 3.1, 3.2, 3.5, 3.6_

  - [ ] 6.2 Write property tests for room filtering
    - **Property 5: Room Display Information** - Validates: Requirements 3.2
    - **Property 6: Filter Application** - Validates: Requirements 3.5

  - [ ] 6.3 Implement POST /api/rooms endpoint
    - Require authentication
    - Validate room name (3-50 chars)
    - Validate description (max 300 chars)
    - Validate genre_tags is non-empty array
    - Generate room taste vector from genre tags
    - Set owner_id to authenticated user
    - Store room in database
    - Return created room with ID
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ] 6.4 Write property tests for room creation
    - **Property 10: Room Name Validation** - Validates: Requirements 5.2
    - **Property 11: Room Description Validation** - Validates: Requirements 5.3
    - **Property 12: Room Persistence** - Validates: Requirements 5.5
    - **Property 13: Room Ownership Assignment** - Validates: Requirements 5.7

  - [ ] 6.5 Implement GET /api/rooms/:room_id endpoint
    - Fetch room by ID from database
    - Return 404 if room not found
    - Return room details including active_jam_link
    - _Requirements: 8.5_

  - [ ] 6.6 Implement POST /api/rooms/:room_id/join endpoint
    - Require authentication
    - Create room_memberships record
    - Increment room user_count
    - Return success response
    - _Requirements: 6.1, 6.2, 6.4_

  - [ ] 6.7 Write property tests for room joining
    - **Property 14: Room Join Membership** - Validates: Requirements 6.1, 6.2
    - **Property 16: User Count Increment** - Validates: Requirements 6.4

  - [ ] 6.8 Implement POST /api/rooms/:room_id/leave endpoint
    - Require authentication
    - Delete room_memberships record
    - Decrement room user_count
    - Return success response
    - _Requirements: 6.5, 6.7_

  - [ ] 6.9 Write property tests for room leaving
    - **Property 17: Room Leave Membership** - Validates: Requirements 6.5
    - **Property 19: User Count Decrement** - Validates: Requirements 6.7

  - [ ] 6.10 Implement PUT /api/rooms/:room_id/jam-link endpoint
    - Require authentication
    - Verify user is room member
    - Validate Spotify Jam link format
    - Update room active_jam_link field
    - Return success response
    - _Requirements: 8.1, 8.2, 8.3, 8.7_

  - [ ] 6.11 Write property tests for Jam link management
    - **Property 26: Spotify Jam Link Validation** - Validates: Requirements 8.2
    - **Property 27: Jam Link Storage** - Validates: Requirements 8.3
    - **Property 29: Jam Link Authorization** - Validates: Requirements 8.7

- [ ] 7. Message API endpoints
  - [ ] 7.1 Implement GET /api/rooms/:room_id/messages endpoint
    - Fetch most recent 50 messages for room
    - Order by created_at descending
    - Return messages with user information
    - _Requirements: 7.5_

  - [ ] 7.2 Write property test for message loading
    - **Property 23: Recent Messages Loading** - Validates: Requirements 7.5

- [ ] 8. Checkpoint - Ensure REST API works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Socket.IO real-time communication
  - [ ] 9.1 Set up Socket.IO server
    - Create socketio_server.py with AsyncServer initialization
    - Configure CORS for Socket.IO
    - Integrate with FastAPI app using ASGIApp
    - _Requirements: 7.1_

  - [ ] 9.2 Implement connection/disconnection handlers
    - Create connect event handler to validate session
    - Store sid to user_id mapping
    - Create disconnect event handler to clean up user state
    - Remove user from all rooms on disconnect
    - _Requirements: 14.4_

  - [ ] 9.3 Write property test for Socket.IO reconnection
    - **Property 46: Socket.IO Reconnection** - Validates: Requirements 14.4

  - [ ] 9.4 Implement join_room event handler
    - Extract room_id from event data
    - Get user_id from sid mapping
    - Create room_memberships record
    - Increment room user_count
    - Join Socket.IO room namespace
    - Broadcast user_joined event to room
    - Broadcast user_count_updated event to room
    - Broadcast active_users_updated event to room
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 9.1, 9.4_

  - [ ] 9.5 Write property tests for join notifications
    - **Property 15: Join Notification Broadcast** - Validates: Requirements 6.3
    - **Property 30: User Count Broadcast** - Validates: Requirements 9.1

  - [ ] 9.6 Implement leave_room event handler
    - Extract room_id from event data
    - Get user_id from sid mapping
    - Delete room_memberships record
    - Decrement room user_count
    - Leave Socket.IO room namespace
    - Broadcast user_left event to room
    - Broadcast user_count_updated event to room
    - Broadcast active_users_updated event to room
    - _Requirements: 6.5, 6.6, 6.7, 9.1, 9.5_

  - [ ] 9.7 Write property tests for leave notifications
    - **Property 18: Leave Notification Broadcast** - Validates: Requirements 6.6

  - [ ] 9.8 Implement send_message event handler
    - Extract room_id and content from event data
    - Get user_id from sid mapping
    - Validate message length (max 500 chars)
    - Sanitize message content (escape HTML)
    - Store message in database
    - Broadcast new_message event to room with message details
    - Update room updated_at timestamp
    - _Requirements: 7.2, 7.3, 7.4, 7.6, 7.7, 9.6_

  - [ ] 9.9 Write property tests for message handling
    - **Property 20: Message Broadcast** - Validates: Requirements 7.2
    - **Property 21: Message Structure** - Validates: Requirements 7.3
    - **Property 22: Message Persistence** - Validates: Requirements 7.4
    - **Property 33: Activity Timestamp Update** - Validates: Requirements 9.6

  - [ ] 9.10 Implement update_jam_link event handler
    - Extract room_id and link from event data
    - Get user_id from sid mapping
    - Verify user is room member
    - Validate Spotify Jam link format
    - Update room active_jam_link field
    - Broadcast jam_link_updated event to room
    - Update room updated_at timestamp
    - _Requirements: 8.2, 8.3, 8.4, 8.7, 9.6_

  - [ ] 9.11 Write property test for Jam link broadcast
    - **Property 28: Jam Link Broadcast** - Validates: Requirements 8.4

- [ ] 10. Frontend - Landing page
  - [ ] 10.1 Create landing page HTML structure
    - Create frontend/index.html with hero section
    - Add "Login with Spotify" button linking to /auth/spotify
    - Add featured rooms preview section
    - Add active user/room count statistics section
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [ ] 10.2 Create landing page styles
    - Create frontend/css/main.css with global styles (dark theme, typography)
    - Create frontend/css/landing.css with hero and preview styles
    - Ensure responsive design for mobile, tablet, desktop
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ] 10.3 Create landing page JavaScript
    - Create frontend/js/landing.js to fetch and display featured rooms
    - Fetch active user/room counts from API
    - Render room previews without authentication
    - _Requirements: 11.4, 11.5_

- [ ] 11. Frontend - Room discovery page
  - [ ] 11.1 Create room discovery HTML structure
    - Create frontend/discover.html with search bar
    - Add genre filter checkboxes
    - Add room cards container
    - Add "Create Room" button and modal
    - _Requirements: 3.1, 3.3, 3.4, 5.1_

  - [ ] 11.2 Create room discovery styles
    - Create frontend/css/discover.css with search, filter, and card styles
    - Style "Highly Recommended" badge
    - Ensure responsive grid layout
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ] 11.3 Create API client utility
    - Create frontend/js/api.js with apiRequest() helper function
    - Implement getRooms(), createRoom(), joinRoom(), getMessages() functions
    - Handle credentials and error responses
    - _Requirements: 3.1, 5.1_

  - [ ] 11.4 Create room discovery JavaScript
    - Create frontend/js/discover.js to load and render rooms
    - Implement search input with debouncing
    - Implement genre filter change handlers
    - Implement createRoomCard() to render room cards with badges
    - Implement room creation modal logic
    - _Requirements: 3.1, 3.2, 3.5, 3.6, 4.5, 5.1_

  - [ ] 11.5 Write property tests for UI display
    - **Property 5: Room Display Information** - Validates: Requirements 3.2
    - **Property 9: High Recommendation Badge** - Validates: Requirements 4.5

- [ ] 12. Frontend - Room chat page
  - [ ] 12.1 Create room chat HTML structure
    - Create frontend/room.html with room header
    - Add active users sidebar
    - Add chat message area (scrollable)
    - Add message input box
    - Add Spotify Jam link section
    - Add leave room button
    - _Requirements: 7.1, 8.1, 9.2, 9.3_

  - [ ] 12.2 Create room chat styles
    - Create frontend/css/room.css with chat layout styles
    - Style message bubbles, user list, and Jam link section
    - Ensure responsive layout for mobile
    - Add smooth transitions for UI updates
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 12.3 Set up Socket.IO client
    - Create frontend/js/socket.js with Socket.IO client initialization
    - Configure withCredentials for cookie authentication
    - Set up connection/disconnection event handlers
    - _Requirements: 7.1, 14.4_

  - [ ] 12.4 Implement room page JavaScript
    - Create frontend/js/room.js to manage room state
    - Load room details and recent messages on page load
    - Emit join_room event on connection
    - Implement sendMessage() function
    - Implement updateJamLink() function
    - Implement leaveRoom() function
    - _Requirements: 7.1, 7.5, 8.1, 6.5_

  - [ ] 12.5 Implement Socket.IO event listeners
    - Listen for user_joined event and update active users list
    - Listen for user_left event and update active users list
    - Listen for new_message event and append to chat
    - Listen for jam_link_updated event and update display
    - Listen for user_count_updated event and update count
    - Listen for active_users_updated event and refresh list
    - Auto-scroll chat to bottom on new messages
    - _Requirements: 6.3, 6.6, 7.2, 8.4, 9.1, 9.4, 9.5_

  - [ ] 12.6 Write property tests for real-time UI updates
    - **Property 31: Active Users Display** - Validates: Requirements 9.2, 9.3
    - **Property 32: Active Users List Update** - Validates: Requirements 9.4, 9.5

- [ ] 13. Error handling and user feedback
  - [ ] 13.1 Implement error response formatting
    - Create error_handlers.py with consistent error response structure
    - Add FastAPI exception handlers for validation errors, auth errors, database errors
    - Return appropriate HTTP status codes (400, 401, 403, 404, 429, 503)
    - _Requirements: 14.2, 14.3, 14.5_

  - [ ] 13.2 Write property tests for error handling
    - **Property 47: Validation Error Display** - Validates: Requirements 14.5
    - **Property 50: Sensitive Data Exclusion** - Validates: Requirements 15.5

  - [ ] 13.3 Implement error logging
    - Configure Python logging module with JSON formatter
    - Log all errors with timestamp, level, message, stack trace, context
    - Log to stdout for container environments
    - _Requirements: 14.6_

  - [ ] 13.4 Write property test for error logging
    - **Property 48: Error Logging** - Validates: Requirements 14.6

  - [ ] 13.5 Implement frontend error display
    - Create showError() utility function in frontend/js/api.js
    - Display error messages in toast notifications or inline alerts
    - Implement showLoading() and hideLoading() for async operations
    - _Requirements: 10.6, 10.7_

  - [ ] 13.6 Write property tests for UI feedback
    - **Property 34: Loading State Display** - Validates: Requirements 10.6
    - **Property 35: Error Message Display** - Validates: Requirements 10.7

- [ ] 14. Security hardening
  - [ ] 14.1 Implement input sanitization across all endpoints
    - Apply sanitize_html() to all user-generated content
    - Validate all inputs before processing
    - Trim whitespace from text inputs
    - _Requirements: 15.3_

  - [ ] 14.2 Write property test for input sanitization
    - **Property 49: Input Sanitization** - Validates: Requirements 15.3

  - [ ] 14.3 Ensure sensitive data exclusion from API responses
    - Remove access_token_encrypted, refresh_token_encrypted from user serialization
    - Remove session tokens from all responses
    - _Requirements: 15.5_

  - [ ] 14.4 Configure HTTPS and secure cookies
    - Set Secure flag on cookies in production
    - Configure HSTS headers
    - Document HTTPS setup in deployment guide
    - _Requirements: 15.2_

- [ ] 15. Deployment preparation
  - [ ] 15.1 Create environment configuration
    - Create .env.example with all required variables
    - Document each environment variable
    - Create config.py to load and validate environment variables
    - _Requirements: 15.1, 15.2_

  - [ ] 15.2 Create database migration scripts
    - Write Alembic migration for initial schema
    - Test migration up and down
    - Document migration commands
    - _Requirements: 12.5, 12.6_

  - [ ] 15.3 Create deployment documentation
    - Write README.md with setup instructions
    - Document local development setup
    - Document production deployment considerations
    - Include Docker setup (optional)
    - _Requirements: All_

  - [ ] 15.4 Create Docker configuration (optional)
    - Create Dockerfile for backend
    - Create docker-compose.yml with backend and PostgreSQL services
    - Test Docker setup locally
    - _Requirements: All_

- [ ] 16. Final checkpoint - End-to-end testing
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Each task references specific requirements for traceability
- Property tests validate universal correctness properties across all inputs
- Unit tests (not marked with `*`) validate specific examples and edge cases
- Checkpoints ensure incremental validation and provide opportunities for user feedback
- The implementation uses Python (FastAPI) for backend and vanilla JavaScript for frontend
- All 51 correctness properties from the design document are mapped to property test tasks
