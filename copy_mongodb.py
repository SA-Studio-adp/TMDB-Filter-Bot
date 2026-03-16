import pymongo
from pymongo.errors import BulkWriteError
from info import DATABASE_URI, DATABASE_URI_2, DATABASE_NAME, DATABASE_NAME_2

def copy_db():
    if not DATABASE_URI or not DATABASE_URI_2:
        print("Error: Both DATABASE_URI and DATABASE_URI_2 must be set in info.py")
        return

    print("Connecting to source database (DATABASE_URI)...")
    try:
        source_client = pymongo.MongoClient(DATABASE_URI)
        source_db = source_client[DATABASE_NAME]
    except Exception as e:
        print(f"Error connecting to source database: {e}")
        return

    print("Connecting to destination database (DATABASE_URI_2)...")
    try:
        dest_client = pymongo.MongoClient(DATABASE_URI_2)
        dest_db = dest_client[DATABASE_NAME_2]
    except Exception as e:
        print(f"Error connecting to destination database: {e}")
        return

    try:
        collections = source_db.list_collection_names()
        print(f"Found collections to copy: {collections}")
    except Exception as e:
        print(f"Error listing collections: {e}")
        return

    for coll_name in collections:
        print(f"\nCopying collection: {coll_name}")
        source_coll = source_db[coll_name]
        dest_coll = dest_db[coll_name]
        
        try:
            docs = list(source_coll.find({}))
            if docs:
                # Use ordered=False to continue inserting even if there's a duplicate key error
                dest_coll.insert_many(docs, ordered=False)
                print(f"Successfully copied {len(docs)} documents for collection '{coll_name}'.")
            else:
                print(f"Collection '{coll_name}' is empty.")
        except BulkWriteError as bwe:
            # This handles ignoring duplicate key errors if the script is run multiple times
            inserted_count = bwe.details.get('nInserted', 0)
            print(f"Copied some documents. {inserted_count} new documents inserted. Duplicate keys were skipped.")
        except Exception as e:
            print(f"Failed to copy collection {coll_name}: {e}")

    print("\nDatabase data successfully copied from 'DATABASE_URI' to 'DATABASE_URI_2'.")

if __name__ == "__main__":
    copy_db()
