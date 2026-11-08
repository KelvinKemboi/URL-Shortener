# URL-Shortener

1. DataBase
- I created a SQL database (sqlite) with SQLAlchemy, and made a database model first
- I chose SQLite because it uses a single file and has Python has integrated support, plus I wanted to start simple
- I then created an engine and connected it to the database, setting a rule that the connection must only be used by the thread that created it
- I then made a helper function to get the session