"""
push_to_github.py - Push local Git repository to GitHub using pure Python (Dulwich).
Allows pushing without requiring a separate Git.exe installation.
"""

import sys
import getpass
from dulwich import porcelain
from dulwich.repo import Repo


def push_repo():
    print("=" * 60)
    print("  Push Enterprise Risk Assistant to Private GitHub Repository")
    print("=" * 60)
    print()

    repo_path = "."
    repo = Repo(repo_path)

    # Ask for GitHub Repo URL
    if len(sys.argv) > 1:
        remote_url = sys.argv[1]
    else:
        remote_url = input("Enter your GitHub repository URL (e.g. https://github.com/username/enterprise-risk-assistant.git): ").strip()

    if not remote_url:
        print("[ERROR] Repository URL is required.")
        return

    # Check if remote exists, otherwise add it
    try:
        porcelain.remote_add(repo, "origin", remote_url)
    except Exception:
        pass  # remote might already exist

    # Ask for authentication
    username = input("Enter your GitHub Username: ").strip()
    token = getpass.getpass("Enter your GitHub Personal Access Token (PAT): ").strip()

    if not token:
        print("[ERROR] Personal Access Token is required to push to a private repository.")
        return

    # Embed auth into HTTPS URL if needed
    if remote_url.startswith("https://"):
        clean_url = remote_url.replace("https://", "")
        auth_url = f"https://{username}:{token}@{clean_url}"
    else:
        auth_url = remote_url

    print()
    print("Pushing to GitHub main branch...")
    try:
        porcelain.push(repo, auth_url, refspecs=["refs/heads/main:refs/heads/main"])
        print("[SUCCESS] Successfully pushed all project code to your GitHub repository!")
        print(f"Repository URL: {remote_url}")
    except Exception as e:
        # Try pushing master/current branch
        try:
            porcelain.push(repo, auth_url, refspecs=["HEAD:refs/heads/main"])
            print("[SUCCESS] Successfully pushed all project code to your GitHub repository!")
            print(f"Repository URL: {remote_url}")
        except Exception as e2:
            print(f"[ERROR] Failed to push: {e2}")
            print("\nTip: Ensure your Personal Access Token (PAT) has 'repo' permissions enabled on GitHub.")


if __name__ == "__main__":
    push_repo()
