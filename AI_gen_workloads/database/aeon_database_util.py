import psycopg2
import psycopg2.extras
import json
import uuid

def connect():
    config = {
        'host': 'us-east-1.68e64730-88a9-4639-8de2-efba5f13e8e1.aws.yugabyte.cloud',
        'port': '5433',
        'dbName': 'yugabyte',
        'dbUser': 'admin',
        'dbPassword': '8GTIG9ng45I80lUPQ_3tNUNA4NgL8h',
        'sslMode': '',
        'sslRootCert': ''
    }

    print(">>>> Connecting to YugabyteDB!")

    try:
        if config['sslMode'] != '':
            yb = psycopg2.connect(host=config['host'], port=config['port'], database=config['dbName'],
                                  user=config['dbUser'], password=config['dbPassword'],
                                  sslmode=config['sslMode'], sslrootcert=config['sslRootCert'],
                                  connect_timeout=10)
        else:
            yb = psycopg2.connect(host=config['host'], port=config['port'], database=config['dbName'],
                                  user=config['dbUser'], password=config['dbPassword'],
                                  connect_timeout=10)
    except Exception as e:
        print("Exception while connecting to YugabyteDB")
        print(e)
        exit(1)

    print(">>>> Successfully connected to YugabyteDB!")
    return yb

def disconnect(yb):
    yb.close()

def create_database():
    yb=connect()
    try:
        with yb.cursor() as yb_cursor:
            yb_cursor.execute('DROP TABLE IF EXISTS Chats')
            yb_cursor.execute('DROP TABLE IF EXISTS Accounts')
            yb_cursor.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"');

            create_table_stmt = """
                    CREATE TABLE IF NOT EXISTS Accounts (
                        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        username VARCHAR(255) UNIQUE,
                        password VARCHAR(255)
                    );
                    CREATE TABLE IF NOT EXISTS Chats (
                        chat_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        name VARCHAR(100),
                        messages JSONB,
                        saved_yb_yaml JSONB,
                        saved_pg_yaml JSONB,
                        acc_id UUID,
                        created_at TIMESTAMP DEFAULT now(),
                        FOREIGN KEY(acc_id) REFERENCES Accounts(id)
                    );
                """
            yb_cursor.execute(create_table_stmt)

        yb.commit()
    except Exception as e:
        print("Exception while creating tables")
        print(e)
        exit(1)
    disconnect(yb)

def create_user(username, password):
    yb=connect()
    try:
        with yb.cursor() as yb_cursor:
            yb_cursor.execute("SELECT * FROM Accounts where username=%s", (username,))
            results = yb_cursor.fetchall()

        if results == []:
            with yb.cursor() as yb_cursor:
                id = uuid.uuid4()
                insert_stmt = "INSERT INTO Accounts(id, username,password) VALUES (%s::uuid, %s, %s)"
                yb_cursor.execute(insert_stmt, (str(id), username, password))
                yb.commit()
            disconnect(yb)
            return {
                "success": True,
                "message": "User created successfully",
                "data": str(id)
            }
        else:
            if results[0][2] == password:
                disconnect(yb)
                return {
                    "success": True,
                    "message": "Login successful",
                    "data": results[0][0]
                }
            else:
                disconnect(yb)
                return {
                    "success": False,
                    "message": "Wrong password",
                    "data": None
                }
    except Exception as e:
        print("Exception : ", e)
        return {
            "success": False,
            "message": f"Exception occurred: {str(e)}",
            "data": None
        }


def store_chat(chat_id, name, acc_id, msgs, yb_yamls, pg_yamls):
    yb = connect()
    try:
        with yb.cursor() as yb_cursor:
            msgs_json = json.dumps(msgs)
            yb_yamls_json = json.dumps(yb_yamls) if not isinstance(yb_yamls, str) else yb_yamls
            pg_yamls_json = json.dumps(pg_yamls) if not isinstance(pg_yamls, str) else pg_yamls
            print(chat_id)
            if chat_id!='-1':
                update_stmt = """
                    UPDATE Chats 
                    SET messages = %s, saved_yb_yaml = %s, saved_pg_yaml = %s 
                    WHERE chat_id = %s
                """
                yb_cursor.execute(update_stmt, (msgs_json, yb_yamls_json, pg_yamls_json, chat_id))
                message = "Chat Updated Successfully!"
                yb.commit()
                return {
                    "success": True,
                    "message": message,
                    "data": chat_id
                }

            else:
                cid = uuid.uuid4()
                print(cid)
                insert_stmt = """
                    INSERT INTO Chats(chat_id, name, messages, saved_yb_yaml, saved_pg_yaml, acc_id)
                    VALUES (%s::uuid, %s, %s, %s, %s, %s::uuid)
                """
                yb_cursor.execute(insert_stmt, (str(cid), name, msgs_json, yb_yamls_json, pg_yamls_json, str(acc_id)))
                message = "Chat Stored Successfully!"
                yb.commit()
                return {
                    "success": True,
                    "message": message,
                    "data": str(cid)
                }

    except Exception as e:
        print("Exception while storing chat")
        print(e)
        return {
            "success": False,
            "message": f"Exception occurred: {str(e)}",
            "data": None
        }
    finally:
        disconnect(yb)

def get_chat(chat_id):
    yb = connect()
    try:
        with yb.cursor() as yb_cursor:
            yb_cursor.execute("SELECT messages, saved_yb_yaml, saved_pg_yaml FROM Chats where chat_id=%s", (chat_id,))
            chat_results = yb_cursor.fetchall()
            disconnect(yb)
            return {
                "success": True,
                "message": "Chat Restored Successfully!",
                "data": chat_results
            }
    except Exception as e:
        print("exception : ",e)
        disconnect(yb)
        return {
            "success": False,
            "message": "Error Occured in fetching Chat!",
            "data": None
        }

def get_chats_history(id):
    yb = connect()
    with yb.cursor() as yb_cursor:
        yb_cursor.execute(
            "SELECT chat_id, name FROM Chats where acc_id=%s ORDER BY created_at DESC",
            (id,))
        chat_results = yb_cursor.fetchall()
    disconnect(yb)
    return {
        "success": True,
        "message": "Login successful",
        "data": chat_results
    }