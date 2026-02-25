# Cloud Setup Guide

This guide walks through setting up all external services needed to run OneShotCourseMate.

---

## 1. Google Cloud Console (OAuth)

### Create a Project
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **Select a project** > **New Project**
3. Name it (e.g., `coursemate`) and click **Create**

### Configure OAuth Consent Screen
1. Navigate to **APIs & Services** > **OAuth consent screen**
2. Select **External** user type, click **Create**
3. Fill in:
   - **App name**: CourseMate
   - **User support email**: your email
   - **Developer contact email**: your email
4. Click **Save and Continue**
5. On **Scopes** page, click **Add or Remove Scopes** and add:
   - `openid`
   - `email`
   - `profile`
6. Click **Save and Continue**
7. On **Test users** page, add your Google email (required while app is in "Testing" status)
8. Click **Save and Continue** > **Back to Dashboard**

### Create OAuth Client ID
1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. Application type: **Web application**
4. Name: `CourseMate Web`
5. **Authorized JavaScript origins** — add all of:
   - `http://localhost:5173` (local development)
   - Your production URL (e.g., `https://your-app.vercel.app`)
6. Leave **Authorized redirect URIs** empty (GIS uses popup flow, no redirects)
7. Click **Create**
8. Copy the **Client ID** (looks like `123456789-xxxxx.apps.googleusercontent.com`)

### Set Environment Variables
Use the same Client ID for both:
```
VITE_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

> **Note**: No Client Secret is needed. Google Identity Services uses the implicit flow with ID tokens, which only requires the Client ID.

### Publishing (for production)
While in "Testing" status, only test users you added can sign in. To allow anyone:
1. Go to **OAuth consent screen**
2. Click **Publish App**
3. If your app requests sensitive scopes, Google may require verification

---

## 2. PostgreSQL Database

### Option A: AWS RDS (Production)

#### Create the Instance
1. Go to [AWS RDS Console](https://console.aws.amazon.com/rds/)
2. Click **Create database**
3. Configuration:
   - **Engine**: PostgreSQL 16
   - **Template**: Free tier
   - **DB instance identifier**: `coursemate-db`
   - **Master username**: `postgres` (or your choice)
   - **Master password**: set a strong password and save it
4. **Connectivity**:
   - **Public access**: Yes (required for Vercel serverless functions)
   - **VPC security group**: Create new or use existing
5. **Additional configuration**:
   - **Initial database name**: `coursemate`
6. Click **Create database** (takes ~5 minutes)

#### Configure Security Group
1. Go to the RDS instance details
2. Click the **VPC security group** link
3. Edit **Inbound rules**:
   - Type: PostgreSQL
   - Port: 5432
   - Source: `0.0.0.0/0` (for Vercel) or restrict to [Vercel's IP ranges](https://vercel.com/docs/security/deployment-protection/ip-allowlist)
4. Save rules

#### Get the Connection URL
1. From the RDS instance details, copy the **Endpoint** (e.g., `coursemate-db.xxxxx.us-east-1.rds.amazonaws.com`)
2. Construct the DATABASE_URL:
```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@coursemate-db.xxxxx.us-east-1.rds.amazonaws.com:5432/coursemate
```

#### Create the database (RDS only, first time)
RDS creates only the default `postgres` database. Create your app database once:
```bash
cd api
DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@coursemate-db.xxxxx.us-east-1.rds.amazonaws.com:5432/coursemate" python create_db.py
```

#### Initialize the schema
```bash
DATABASE_URL="postgresql://..." python init_db.py
```

### Option B: Local PostgreSQL (Development)

#### macOS (Homebrew)
```bash
brew install postgresql@16
brew services start postgresql@16
createdb coursemate
```

#### Docker
```bash
docker run -d \
  --name coursemate-db \
  -e POSTGRES_DB=coursemate \
  -e POSTGRES_PASSWORD=devpassword \
  -p 5432:5432 \
  postgres:16
```

#### Set DATABASE_URL
```
DATABASE_URL=postgresql://postgres:devpassword@localhost:5432/coursemate
```

#### Initialize
```bash
cd api
DATABASE_URL="postgresql://postgres:devpassword@localhost:5432/coursemate" python init_db.py
```

---

## 3. Session Secret

Generate a cryptographically secure secret for CSRF token signing:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Set it in your `.env`:
```
SESSION_SECRET=<the-64-char-hex-string>
```

---

## 4. Vercel Deployment (Import from GitHub)

Follow these steps exactly to deploy OneShotCourseMate from your GitHub repository.

### 4.1 Sign in to Vercel
1. Open [vercel.com](https://vercel.com) in your browser.
2. Click **Sign Up** or **Log In**.
3. Choose **Continue with GitHub** and authorize Vercel to access your GitHub account.

### 4.2 Import the project
1. From the Vercel dashboard, click **Add New…** → **Project**.
2. You should see **Import Git Repository**. If your GitHub account is not connected, click **Connect Git Repository** and connect **GitHub**, then return to **Add New…** → **Project**.
3. Find your repository (e.g. `ShubhanYenuganti/coursemate-public`) in the list and click **Import** next to it.

### 4.3 Configure the project
1. **Project Name**: Leave the default (e.g. `coursemate-public`) or set a name like `coursemate`. This will be used in the URL: `https://<project-name>.vercel.app`.
2. **Root Directory**: Leave as **.** (root). Do not change unless the app lives in a subfolder of the repo.
3. **Framework Preset**: Vercel should auto-detect **Vite**. If not, select **Vite**.
4. **Build and Output Settings** (usually correct by default):
   - **Build Command**: `npm run build` or `vite build`
   - **Output Directory**: `dist`
   - **Install Command**: `npm install`
5. Do **not** click **Deploy** yet. Click **Environment Variables** to expand it (or continue to the next step and add variables before deploying).

### 4.4 Add environment variables (before first deploy)
1. In the **Environment Variables** section on the same page, add each variable below. For **Environment**, select **Production**, **Preview**, and **Development** for each (or at least Production and Preview).
2. Add these one by one:

| Name | Value | Environments |
|------|--------|--------------|
| `VITE_GOOGLE_CLIENT_ID` | Your Google OAuth Client ID (e.g. `223353249861-xxx.apps.googleusercontent.com`) | Production, Preview, Development |
| `GOOGLE_CLIENT_ID` | Same value as `VITE_GOOGLE_CLIENT_ID` | Production, Preview, Development |
| `DATABASE_URL` | `postgresql://postgres:YOUR_PASSWORD@your-rds-endpoint:5432/coursemate` (your full RDS URL) | Production, Preview, Development |
| `SESSION_SECRET` | The 64-character hex string you generated (see Section 3) | Production, Preview, Development |
| `ALLOWED_ORIGIN` | Leave empty for now; you will set it after the first deploy (see 4.6) | Production |
| `RATE_LIMIT_RPM` | `30` (optional) | Production |

3. For **ALLOWED_ORIGIN**: After the first deploy you will get a URL like `https://coursemate-public.vercel.app`. You will come back and set `ALLOWED_ORIGIN` to that URL (including `https://`, no trailing slash).
4. Click **Deploy** to start the first deployment.

### 4.5 Wait for deployment
1. Wait for the build to finish. If the build fails, check the build log (e.g. missing env var or wrong Node version).
2. When it succeeds, Vercel shows **Congratulations!** and a **Visit** link. Click **Visit** to open the live site. Copy the URL (e.g. `https://coursemate-public.vercel.app`).

### 4.6 Set production URL in Vercel and Google
1. In Vercel, go to your project → **Settings** → **Environment Variables**.
2. Find **ALLOWED_ORIGIN**. If you left it empty, add it now; if it exists, edit it. Set the value to your production URL exactly, e.g. `https://coursemate-public.vercel.app` (no trailing slash). Apply to **Production** (and optionally Preview).
3. In **Google Cloud Console** → **APIs & Services** → **Credentials** → your OAuth 2.0 Client ID → edit.
4. Under **Authorized JavaScript origins**, add: `https://coursemate-public.vercel.app` (use your actual Vercel URL). Save.
5. In Vercel, go to **Deployments**, open the **⋯** menu on the latest deployment, and click **Redeploy** so that the new `ALLOWED_ORIGIN` and Google origin are used.

### 4.7 Later deploys (automatic from GitHub)
- Pushes to the default branch (e.g. `main`) trigger production deploys.
- Other branches get Preview deployments with unique URLs. No need to run the CLI unless you want to deploy from your machine.

### 4.8 Optional: deploy from your machine with CLI
```bash
npm i -g vercel
vercel login
vercel --prod
```
Use this only if you are not using GitHub integration or want to deploy from a local branch.

---

## 5. Summary Checklist

- [ ] Google Cloud project created
- [ ] OAuth consent screen configured with scopes
- [ ] OAuth Client ID created (JavaScript origins can be updated after first Vercel deploy)
- [ ] PostgreSQL database running (RDS or local)
- [ ] RDS: database created (`python create_db.py`) and schema initialized (`python init_db.py`); local: `python init_db.py` only
- [ ] `.env` file created locally with all variables from `.env.example`
- [ ] `SESSION_SECRET` generated
- [ ] (Vercel) GitHub repo connected and project imported
- [ ] (Vercel) Environment variables set: `VITE_GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_ID`, `DATABASE_URL`, `SESSION_SECRET`; then `ALLOWED_ORIGIN` after first deploy
- [ ] (Vercel) Production URL added to Google Console **Authorized JavaScript origins**
- [ ] (Vercel) Redeployed after setting `ALLOWED_ORIGIN` and Google origin
