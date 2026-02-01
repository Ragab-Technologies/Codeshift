## 🎯 Overview

Enable users to create, share, and install custom migration templates for internal libraries or custom patterns, creating a marketplace ecosystem.

## 💡 Value Proposition

**For Users:**
- **Enterprise Value**: Codify internal library migration patterns
- **Extensibility**: Make tool valuable for ANY library
- **Knowledge Sharing**: Learn from community best practices
- **Consistency**: Standardize migrations across teams

**For Business:**
- **Network Effects**: User-generated content creates moat
- **Revenue Opportunity**: Marketplace with revenue sharing (70/30 split)
- **Enterprise Adoption**: Companies pay for private template storage
- **Platform Play**: Becomes infrastructure for Python ecosystem

## ✨ Features

- Template creation wizard (interactive CLI)
- Template validation and testing framework
- Template marketplace (cloud-based)
- Import/export templates as YAML
- Template versioning and updates
- Search and discovery
- Ratings and reviews
- Private templates for enterprises
- Revenue sharing for paid templates

## 🎨 Usage Example

### Creating a Template
```bash
$ codeshift template create

Template Creation Wizard
========================

1. Library name: my-company-auth
2. Source version: 1.x
3. Target version: 2.x
4. Description: Migrate internal auth library v1 to v2

Define transforms:
[1] Import rename: old_auth → new_auth
[2] Function call: authenticate_user(...) → authenticate(...)

Template saved to: ~/.codeshift/templates/my-company-auth.yaml

Publish to marketplace? [y/N]: y
✅ Published!
```

### Using a Template
```bash
$ codeshift template search django

Found 3 templates:
1. django-custom-auth (★★★★★ 4.8, 1.2K uses)
   Author: @django-expert | Price: Free
   
2. django-rest-framework-v4 (★★★★☆ 4.5, 450 uses)
   Author: @rest-guru | Price: $5/migration

$ codeshift template install django-custom-auth
✅ Installed

$ codeshift upgrade django-custom-auth --target 2.0.0
Using custom template...
```

## 🏗️ Technical Implementation

### Template YAML Format
```yaml
name: internal-auth-lib
version: "1.0.0"
description: Migration for internal auth library
library: my-company-auth
source_version: "1.x"
target_version: "2.x"

transforms:
  - type: import_rename
    from_import: "my_company_auth.old_auth"
    to_import: "my_company_auth.new_auth"
    confidence: HIGH
    
  - type: function_call_transform
    function: "authenticate_user"
    pattern: "authenticate_user\\(username=(?P<user>\\w+), password=(?P<pwd>\\w+)\\)"
    replacement: "authenticate(user=\\g<user>, pwd=\\g<pwd>, method='password')"
    confidence: HIGH

test_cases:
  - name: "Import transformation"
    before: |
      from my_company_auth.old_auth import authenticate_user
    after: |
      from my_company_auth.new_auth import authenticate
```

### CLI Commands
```bash
# Management
codeshift template create                    # Interactive wizard
codeshift template test <template.yaml>      # Test template
codeshift template publish                   # Publish to marketplace
codeshift template unpublish <name>          # Remove

# Discovery
codeshift template search <query>            # Search marketplace
codeshift template install <name>            # Install template
codeshift template list                      # List installed
```

## 📦 Server-Side Requirements

### API Endpoints
```python
# Marketplace
GET    /api/templates                    # List templates
GET    /api/templates/search             # Search
POST   /api/templates                    # Publish
GET    /api/templates/{id}               # Details
GET    /api/templates/{id}/download      # Download YAML

# Reviews
GET    /api/templates/{id}/reviews       # Get reviews
POST   /api/templates/{id}/reviews       # Add review
```

### Database Schema
```sql
CREATE TABLE templates (
    id UUID PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    author_id UUID REFERENCES auth.users(id),
    library_name TEXT,
    source_version TEXT,
    target_version TEXT,
    template_yaml TEXT,
    downloads INTEGER DEFAULT 0,
    uses INTEGER DEFAULT 0,
    rating_avg DECIMAL(3,2),
    is_public BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    price_per_use DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE template_reviews (
    id UUID PRIMARY KEY,
    template_id UUID REFERENCES templates(id),
    user_id UUID REFERENCES auth.users(id),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE template_usage (
    id UUID PRIMARY KEY,
    template_id UUID REFERENCES templates(id),
    user_id UUID REFERENCES auth.users(id),
    success BOOLEAN,
    used_at TIMESTAMPTZ DEFAULT now()
);
```

## 📋 Implementation Tasks

### Phase 1: Core Template Engine (Weeks 1-2)
- [ ] Design YAML template format
- [ ] Implement parser and validator
- [ ] Create template executor
- [ ] Add basic transforms (import, function, class)

### Phase 2: CLI & Local Storage (Weeks 3-4)
- [ ] Template CLI commands
- [ ] Interactive creation wizard
- [ ] Local template storage
- [ ] Testing framework

### Phase 3: Marketplace API (Weeks 5-6)
- [ ] Database schema implementation
- [ ] FastAPI endpoints
- [ ] Search and filtering
- [ ] Download tracking

### Phase 4: Reviews & Ratings (Weeks 7-8)
- [ ] Review system (backend + CLI)
- [ ] Rating aggregation
- [ ] Featured/trending algorithms
- [ ] Verification workflow

### Phase 5: Paid Templates (Weeks 9-10)
- [ ] Stripe integration
- [ ] Usage-based billing
- [ ] Revenue sharing (70/30)
- [ ] Creator payouts

### Phase 6: Polish & Launch (Weeks 11-12)
- [ ] Testing (unit, integration, E2E)
- [ ] Documentation
- [ ] Example templates
- [ ] Public launch

## 📊 Success Metrics

- 100+ community templates within 6 months
- 30% of Pro users create at least one template
- $5K+ MRR from marketplace
- 90%+ templates have 4+ star rating

## 💰 Revenue Model

### Creator Economics
```
Template price: $5/use
Uses per month: 100
Revenue: $500/month

Creator share (70%): $350/month
Codeshift share (30%): $150/month

Top creator potential: $3,500+/month
```

### Pricing Tiers
| Feature | Free | Pro ($19/mo) | Team ($49/mo) |
|---------|------|--------------|---------------|
| Install templates | ✅ | ✅ | ✅ |
| Create public | ✅ | ✅ | ✅ |
| Private templates | 1 | 5 | Unlimited |
| Revenue share | ❌ | 70% | 70% + priority |

## 🚀 Future Enhancements

- AI-generated templates from examples
- Template bundles
- Enterprise template galleries
- Automated testing service
- Web-based template editor
- Community voting for verification

---

**Priority**: 🟡 High  
**Effort**: 📊 2-3 months  
**Impact**: 📈 Very High  
**Revenue Potential**: 💰 Very High

**Full Specification**: See `docs/FEATURE_PROPOSALS.md` Section 2
