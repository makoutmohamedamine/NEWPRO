import psycopg2
import sys
import getpass

def create_database():
    print("=== Création de la base de données PostgreSQL ===")
    db_name = input("Nom de la base de données à créer [cv_db] : ").strip() or "cv_db"
    db_user = input("Utilisateur PostgreSQL [postgres] : ").strip() or "postgres"
    db_password = getpass.getpass("Mot de passe PostgreSQL : ").strip()
    db_host = input("Hôte PostgreSQL [localhost] : ").strip() or "localhost"
    db_port = input("Port PostgreSQL [5432] : ").strip() or "5432"

    try:
        # Connexion au serveur PostgreSQL par défaut (base "postgres")
        conn = psycopg2.connect(
            dbname="postgres",
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Vérifier si la base existe déjà
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (db_name,))
        exists = cursor.fetchone()

        if not exists:
            cursor.execute(f'CREATE DATABASE "{db_name}"')
            print(f"\n[SUCCÈS] La base de données '{db_name}' a été créée avec succès !")
        else:
            print(f"\n[INFO] La base de données '{db_name}' existe déjà.")

        cursor.close()
        conn.close()

        print("\n=== Étapes suivantes ===")
        print("1. Ouvrez le fichier backend/.env")
        print("2. Décommentez et remplissez les lignes concernant la base de données :")
        print(f"   DB_NAME={db_name}")
        print(f"   DB_USER={db_user}")
        print(f"   DB_PASSWORD=votre_mot_de_passe")
        print(f"   DB_HOST={db_host}")
        print(f"   DB_PORT={db_port}")
        print("\n3. Appliquez les migrations avec : python manage.py migrate")
        
    except Exception as e:
        print(f"\n[ERREUR] Impossible de créer la base de données : {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_database()
