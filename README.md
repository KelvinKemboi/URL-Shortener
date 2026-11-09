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

 4. Request body 
 - Use basemodel from pydantic for this since its produces schema for expected dat
 - Expected data is original url in HttpUrl form
 - Have it substitute parameters in shorten url and parse to string in function

 5. Clicks stats
 - SQLModel to store the clicks data, with link id specific to each link
 - After every redirect, add a link count to the table
 - Use get and retrieve clicks count for that specific link id
