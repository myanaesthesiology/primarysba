Primary-DISC02 — Firebase-connected discussions

Deployment
==========
1. Publish firestore.rules from this package in Firebase Console > Firestore Database > Rules.
   This DISC02 version adds the private userDiscussionThreads index needed for an accurate
   "My discussions" tab.
2. Confirm Authentication > Sign-in method > Anonymous is enabled.
3. Confirm your deployed hostname (for example myanaesthesiology.github.io) appears under
   Authentication > Settings > Authorized domains.
4. Upload index.html, manifest.webmanifest, service-worker.js, firebase-config.js and icons/
   together at the same web path.
5. Open the site online once. The service worker will update to DISC02.

Implemented
===========
- Firebase JS SDK 12.18.0 loaded dynamically only when discussions are configured/online.
- Anonymous Authentication with LOCAL browser persistence.
- Shared threads keyed primary-q-1 through primary-q-1102.
- Live thread list and live question comments.
- Root comments and reply-to-comment/reply-to-reply, rendered at one visual reply level.
- Author-only soft delete; replies remain.
- Reports collection.
- Accurate My discussions index private to the current anonymous UID.
- Firebase failures/offline state do not block the SBA bank.

The Firebase Web API key/config is a normal client configuration identifier, not a service-account secret.
