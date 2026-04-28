import base64
from collections import OrderedDict
from string import Template
from typing import List
from PyPDF2 import PdfMerger, PdfReader
from weasyprint import HTML
from io import BytesIO

from logic.pdf.dtos.pdf_dtos import GeneratePDFDTO

class PDFManager:
    def __init__(self, dto: GeneratePDFDTO):
        self.dto = dto
        self.TEMPLATE_ID_TO_PDF_FILENAME_MAP = {
            "order.create.erw_angles": "templates/pdf/create_order_erw_angles_pdf.html",
            "order.create.tmt": "templates/pdf/create_order_pdf.html",
            "order.create.fmcg": "templates/pdf/create_order_fmcg_pdf.html",
            "purchase_order.create": "templates/pdf/create_purchase_order_pdf.html",
        }

        self.deliver_to_details = OrderedDict()

    def execute(self):
        self._get_pdf_template()
        self._validate_content()
        self._prepare_stp_details()
        self._prepare_pdf_pages()
    
    def get_pdf_attachments(self):
        return self.attachments

    def _get_pdf_template(self):
        self.pdf_template = self.TEMPLATE_ID_TO_PDF_FILENAME_MAP.get(self.dto.template_id)
        if not self.pdf_template:
            raise ValueError(f"Invalid template_id: {self.dto.template_id}")
    
    def _validate_content(self):
        # Additional validation logic can be added here based on the template_id
        if not self.dto.content:
            raise ValueError("Content cannot be empty")
        
        if "delivery_details" not in self.dto.content:
            raise ValueError("Each item in content must include 'delivery_details' field")
        if "bill_to_party" not in self.dto.content:
            raise ValueError("Each item in content must include 'bill_to_party' field")
        if "order_detail" not in self.dto.content:
            raise ValueError("Each item in content must include 'order_detail' field")
        
        if self.dto.content.get("delivery_details") is None:
            raise ValueError("'delivery_details' field cannot be null")
        
    def _prepare_stp_details(self):
        delivery_details = self.dto.content.get("delivery_details", [])
        for item in delivery_details:
            ship_to_party = item.get("ship_to_party", {})
            products_info = item.get("products_info", [])

            print(f"Preparing PDF page for ship_to_party: {ship_to_party}")
            print(f"Product info: {products_info}")

            stp_total_quantity = 0

            stp_key = (ship_to_party.get("stp_id"), ship_to_party.get("address"))

            for product in products_info:
                qty = product.get("quantity", 0)
                price_per_unit = product.get("price_per_unit", 0)
                product_name = product.get("product_name", "")
                form_type = product.get("form_type", "")
                delivery_type = product.get("delivery_type", "")
                uom = product.get("unit", "Ton")
                remark = product.get("remark", "")

                total_price = round(price_per_unit * qty, 2)
                stp_total_quantity += qty

                # HTML row creation (cleaned)
                row_html = (
                    f'<tr style="text-align: center;">'
                    f'<td>{product_name}</td>'
                    f'<td>{form_type}</td>'
                    f'<td>{delivery_type}</td>'
                    f'<td>{uom}</td>'
                    f'<td>{qty}</td>'
                    f'<td>{round(price_per_unit, 2)}</td>'
                    f'<td>{total_price}</td>'
                    f'<td>{remark}</td>'
                    f'</tr>'
                )

                # Initialize if not exists
                if stp_key not in self.deliver_to_details:
                    self.deliver_to_details[stp_key] = {
                        "deliver_to_company_name": ship_to_party.get("name", ""),
                        "deliver_to_company_addr": ship_to_party.get("address", ""),
                        "deliver_to_company_gst": ship_to_party.get("gstin", ""),
                        "deliver_to_company_pan": ship_to_party.get("pancard_no", ""),
                        "deliver_to_company_contact": ship_to_party.get("phone_no", ""),
                        "total_quantity": 0,
                        "total_price": 0,
                        "form_type": form_type,
                        "delivery_type": delivery_type,
                        "deliver_to_products": [],
                    }

                # Update aggregates
                entry = self.deliver_to_details[stp_key]
                entry["total_quantity"] += qty
                entry["total_price"] += total_price
                entry["deliver_to_products"].append(row_html)
    
    def _prepare_pdf_pages(self):
        # Implement logic to prepare PDF pages based on the deliver_to_details
        display_distributor = True
        pages = []
        for stp_key, details in self.deliver_to_details.items():
            print(f"Preparing PDF page for STP: {stp_key}")
            print(f"Details: {details}")
            page = self.__prepare_page(stp_detail=details, display_distributor=display_distributor)
            display_distributor = False  # Only display distributor details on the first page
            # Here you would typically render the HTML template with the details and convert it to PDF
            pages.append(page)
        
        if len(pages) > 1:
            ## Merging PDFs
            pdf_merged = self.__merge_pdfs(pages)
            if pdf_merged is None:
                print("PDF merging failed, using individual pages as attachments")
            pdfs_base64 = [base64.b64encode(pdf_bytes).decode() for pdf_bytes in pdf_merged]
        else:
            pdfs_base64 = pages

        self.attachments = [
            {
                "file_name": f"{self.dto.template_id}_{index + 1}.pdf",
                "base64": pdf_base64
            }
            for index, pdf_base64 in enumerate(pdfs_base64)
        ]
    
    def __prepare_page(self, stp_detail: dict, display_distributor: bool = False):
        btp_detail = self.dto.content.get("bill_to_party")
        btp_name = btp_detail.get("name", "")
        btp_addr = btp_detail.get("address", "")
        btp_gst = btp_detail.get("gstin", "")
        btp_pan = btp_detail.get("pancard_no", "")

        stp_delivery_type = stp_detail.get("delivery_type", "")
        stp_name = stp_detail.get("deliver_to_company_name", "")
        stp_addr = stp_detail.get("deliver_to_company_addr", "")
        stp_gst = stp_detail.get("deliver_to_company_gst", "")
        stp_pan = stp_detail.get("deliver_to_company_pan", "")
        stp_phone = stp_detail.get("deliver_to_company_contact", "")
        stp_products = stp_detail.get("deliver_to_products", [])
        stp_products_joined = "".join(stp_products)
        stp_total_qty = stp_detail.get("total_quantity", 0)
        stp_total_price = stp_detail.get("total_price", 0)

        order_detail = self.dto.content.get("order_detail", {})
        order_id = order_detail.get("order_id", "")
        order_date = order_detail.get("order_date", "")
        user_po_number = order_detail.get("user_po_number", "")
        documented_date = order_detail.get("documented_date", "")
        humbee_po_number = order_detail.get("humbee_po_number", "")
        po_no_and_date = f"{humbee_po_number}/{documented_date}"
        
        with open(self.pdf_template, 'r', encoding='utf-8') as f:
            html = f.read()

        template = Template(html)

        template = template.substitute(
            distributor_company_name=btp_name,
            distributor_company_addr=btp_addr,
            distributor_company_gst=btp_gst,
            distributor_company_pan=btp_pan,
            order_delivery_type_1=stp_delivery_type,
            buyer1_company_name=stp_name,
            buyer1_company_addr=stp_addr,
            buyer1_company_gst=stp_gst,
            buyer1_company_pan=stp_pan,
            buyer1_company_contact=stp_phone,
            buyer1_details=stp_products_joined,
            buyer1_product_total=stp_total_qty,
            humbee_order_id=order_id,
            user_po_id=user_po_number,
            po_no_and_date=po_no_and_date,
            humbee_order_date=order_date,
            total_price=stp_total_price,
            distributor_display_val='block' if display_distributor else 'none'
        )
        pdf_base64 = self.__convert_to_pdf(template=template)
        return pdf_base64

    def __merge_pdfs(self, pdf_list: List[str]):
        merger = PdfMerger()
        for pdf in pdf_list:
            try:
                print("Merging pdfs.... PROCESSING...")
                pdf_content = base64.b64decode(pdf)
                pdf_io = BytesIO(pdf_content)
                pdf_reader = PdfReader(pdf_io)
                merger.append(pdf_reader)
                print("Merging pdfs.... COMPLETED...")
            except Exception as e:
                print(f"An error occured while merging pdfs: {e}")
                return None
        output_io = BytesIO()
        merger.write(output_io)

        output_data = output_io.getvalue()
        print(f"return pdf data: {[output_data]}")
        return [output_data]
    
    def __convert_to_pdf(self, template):
        print("Converting HTML to PDF using pdfkit...")
        pdf = HTML(string=template).write_pdf()
        encoded = base64.b64encode(pdf).decode()
       
        print("Encoded pdf html bytes to base64")
        return encoded
    