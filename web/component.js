
export class Component extends HTMLElement {
  constructor(hooked_attributes=[]) {
    super();
    this._hooked_attributes = {};
    this._setupSetattr(hooked_attributes);
    this.attachShadow({mode: 'open'});
  }

  _setupSetattr(hooked_attributes) {
    for (const attr of hooked_attributes) {
      this._hooked_attributes[attr] = null;
      Object.defineProperty(this, attr, {
        get() { return this._hooked_attributes[attr]; },
        set(value) {
          new Promise(this._onHookedAttributeChanged.bind(this, attr, value)).then(
            result => {this._hooked_attributes[attr] = value;},
            error => {console.log(error);}
          );
        }
      });
      if (this.hasAttribute(attr)) {
        new Promise(this._onHookedAttributeChanged.bind(this, attr, this.getAttribute(attr))).then(
          result => {this._hooked_attributes[attr] = this.getAttribute(attr);},
          error => {console.log(error);}
        );
      }
    }
  }

  _onHookedAttributeChanged(attr, value, resolve, reject) {
    if (this.setattr(attr, value))
      resolve()
    else
      reject();
  }

  fetchUrlData()

  setattr(attr, value) {
    return true;
  }

  appendChild(node) {
    this.shadowRoot.appendChild(node);
  }

  removeChild(node) {
    this.shadowRoot.removeChild(node);
  }

  get children() {
    return this.shadowRoot.children;
  }

  get firstChild() {
    return this.shadowRoot.firstChild;
  }

  get innerHTML() {
    return this.shadowRoot.innerHTML;
  }

  set innerHTML(innerHTML) {
    this.shadowRoot.innerHTML = innerHTML;
  }

  get innerText() {
    return this.shadowRoot.innerText;
  }

  set innerText(innerText) {
    this.shadowRoot.innerText = innerText;
  }
};