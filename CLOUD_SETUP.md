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

## 4. Vercel Deployment

### Install Vercel CLI
```bash
npm i -g vercel
vercel login
```

### Set Environment Variables
In the [Vercel Dashboard](https://vercel.com) > your project > **Settings** > **Environment Variables**, add:

| Variable | Value | Environment |
|----------|-------|-------------|
| `VITE_GOOGLE_CLIENT_ID` | Your Google Client ID | Production, Preview, Development |
| `GOOGLE_CLIENT_ID` | Same Google Client ID | Production, Preview, Development |
| `DATABASE_URL` | Your PostgreSQL connection string | Production, Preview, Development |
| `SESSION_SECRET` | Your generated secret | Production, Preview, Development |
| `ALLOWED_ORIGIN` | `https://your-app.vercel.app` | Production |
| `RATE_LIMIT_RPM` | `30` (optional) | Production |

### Update Google Console
Add your Vercel production URL to **Authorized JavaScript origins** in Google Cloud Console.

### Deploy
```bash
vercel --prod
```

---

## 5. Summary Checklist

- [ ] Google Cloud project created
- [ ] OAuth consent screen configured with scopes
- [ ] OAuth Client ID created with correct JavaScript origins
- [ ] PostgreSQL database running (RDS or local)
- [ ] Database schema initialized (`python init_db.py`)
- [ ] `.env` file created with all variables from `.env.example`
- [ ] `SESSION_SECRET` generated
- [ ] `ALLOWED_ORIGIN` set correctly
- [ ] (Production) Vercel environment variables configured
- [ ] (Production) Production URL added to Google Console origins
