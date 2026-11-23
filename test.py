from registry.permission import get_google_services
import os

if __name__ == "__main__":
    # Delete old tokens if forcing a fresh re-auth
    for acc in ["personal", "business"]:
        tf = f"token_{acc}.json"
        if os.path.exists(tf):
            os.remove(tf)

    get_google_services("personal")
    get_google_services("business")
    print("\n[COMPLETE] Both tokens generated with permanent refresh access!")