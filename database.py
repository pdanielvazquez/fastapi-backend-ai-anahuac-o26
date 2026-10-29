from motor.motor_asyncio import AsyncIOMotorClient

# URL de conexión a mongodb
MONGO_URL = "mongodb+srv://pdanielvazquez_db_user:eMSYb7iAzx0MYpaK@cluster0.54drn85.mongodb.net/"

# Conexión al cliente
client = AsyncIOMotorClient(MONGO_URL)

# Selección de base de datos
database = client.mibasededatos

# Selección de una colección
collection = database.get_collection("micoleccion")