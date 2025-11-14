-- schema_and_data.sql
CREATE DATABASE IF NOT EXISTS dbms_project;
USE dbms_project;

DROP TABLE IF EXISTS User_channel;
DROP TABLE IF EXISTS Post_tag;
DROP TABLE IF EXISTS MESSAGE;
DROP TABLE IF EXISTS COMMENT;
DROP TABLE IF EXISTS TAG;
DROP TABLE IF EXISTS POST;
DROP TABLE IF EXISTS CHANNEL;
DROP TABLE IF EXISTS USER;

CREATE TABLE USER (
    user_id INT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100),
    password_hash VARCHAR(255),
    year INT,
    department VARCHAR(100),
    bio VARCHAR(255),
    created_on DATE
);

CREATE TABLE CHANNEL (
    channel_id INT PRIMARY KEY,
    channel_name VARCHAR(100),
    description VARCHAR(255)
);

CREATE TABLE POST (
    post_id INT PRIMARY KEY,
    user_id INT,
    title VARCHAR(150),
    content TEXT,
    category VARCHAR(100),
    Created_on DATE,
    channel_id INT,
    likes INT DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES USER(user_id),
    FOREIGN KEY (channel_id) REFERENCES CHANNEL(channel_id)
);

CREATE TABLE TAG (
    tag_id INT PRIMARY KEY,
    tag_name VARCHAR(100)
);

CREATE TABLE COMMENT (
    comment_id INT PRIMARY KEY,
    post_id INT,
    user_id INT,
    comment_text TEXT,
    timestamp DATETIME,
    FOREIGN KEY (post_id) REFERENCES POST(post_id),
    FOREIGN KEY (user_id) REFERENCES USER(user_id)
);

CREATE TABLE MESSAGE (
    message_id INT PRIMARY KEY,
    user_id INT,
    channel_id INT,
    message_text TEXT,
    timestamp DATETIME,
    FOREIGN KEY (user_id) REFERENCES USER(user_id),
    FOREIGN KEY (channel_id) REFERENCES CHANNEL(channel_id)
);

CREATE TABLE Post_tag (
    Post_id INT,
    Tag_id INT,
    PRIMARY KEY (Post_id, Tag_id),
    FOREIGN KEY (Post_id) REFERENCES POST(post_id),
    FOREIGN KEY (Tag_id) REFERENCES TAG(tag_id)
);

CREATE TABLE User_channel (
    User_id INT,
    Channel_id INT,
    PRIMARY KEY (User_id, Channel_id),
    FOREIGN KEY (User_id) REFERENCES USER(user_id),
    FOREIGN KEY (Channel_id) REFERENCES CHANNEL(channel_id)
);

-- Sample data (you can expand)
INSERT INTO USER VALUES 
(1, 'Alice', 'alice@pes.edu', 'hash1', 3, 'CSE', 'Tech enthusiast', '2025-01-01'),
(2, 'Bob', 'bob@pes.edu', 'hash2', 3, 'CSE', 'DBMS mini project', '2025-02-01');

INSERT INTO CHANNEL VALUES 
(10, 'General', 'General discussion'),
(11, 'DBMS', 'Database related posts');

INSERT INTO TAG VALUES 
(201, 'SQL'),
(202, 'DBMS');

INSERT INTO POST VALUES 
(1001, 1, 'Database Normalization', 'Explaining 3NF', 'Education', '2025-03-15', 11, 5),
(1002, 2, 'Triggers in MySQL', 'Trigger examples', 'Education', '2025-03-20', 11, 2);

-- Your inserted comment (kept exactly)
INSERT INTO COMMENT VALUES 
(503, 1001, 2, 'Testing trigger', '2025-04-01 12:00:00');

-- Additional comment for testing trigger
INSERT INTO COMMENT VALUES 
(504, 1001, 1, 'Second test comment', '2025-04-02 09:00:00');

INSERT INTO MESSAGE VALUES
(301, 1, 10, 'Hey everyone!', '2025-03-20 10:30:00'),
(302, 2, 11, 'Can anyone explain triggers?', '2025-03-22 11:00:00');

INSERT INTO Post_tag VALUES
(1001, 201),
(1002, 202);

INSERT INTO User_channel VALUES
(1, 10),
(2, 11);

-- TRIGGER (example: increment POST.likes when COMMENT inserted)
DELIMITER $$
DROP TRIGGER IF EXISTS comment_added$$
CREATE TRIGGER comment_added
AFTER INSERT ON COMMENT
FOR EACH ROW
BEGIN
  UPDATE POST
  SET likes = likes + 1
  WHERE post_id = NEW.post_id;
END$$
DELIMITER ;

-- Function: returns number of comments for a post (name matches your schema style)
DELIMITER $$
DROP FUNCTION IF EXISTS commentCount$$
CREATE FUNCTION commentCount(p_id INT)
RETURNS INT
DETERMINISTIC
BEGIN
  DECLARE c INT;
  SELECT COUNT(*) INTO c FROM COMMENT WHERE post_id = p_id;
  RETURN c;
END$$
DELIMITER ;

-- Procedure: get posts by channel
DELIMITER $$
DROP PROCEDURE IF EXISTS GetPostsByChannel$$
CREATE PROCEDURE GetPostsByChannel(IN ch_id INT)
BEGIN
  SELECT p.post_id, p.title, p.content, u.name AS posted_by, p.Created_on
  FROM POST p
  JOIN USER u ON p.user_id = u.user_id
  WHERE p.channel_id = ch_id;
END$$
DELIMITER ;
