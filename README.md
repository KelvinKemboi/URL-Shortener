# URL-Shortener

1. DataBase
- I created a SQL database (sqlite) with SQLAlchemy, and made a database model first
- I chose SQLite because it uses a single file and has Python has integrated support, plus I wanted to start simple
- I then created an engine and connected it to the database, setting a rule that the connection must only be used by the thread that created it
- I then made a helper function to get the session

2. Short code
- Takes the URL and associates it with the short code
- Allows for a user to input their own custom code
- Short code has to have letters/numbers/_ only

3. Redirecting
- Looks up the short code in the databse and returns the link
- Raises 404 status error when link not found
- Redirects to the original url

Note: 307 is the right choice
 - Status 307 is temporary so every visit goes through my server. It's good for analytics and expiring links. Similar to 302
 - Status 301 is permanent so the long url is cached meaning the server is not visited again but retrieval is from cached memory. Is fast and cheap, but will break analytics and is not good for expiring links
