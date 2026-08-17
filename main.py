from flask import Flask, request, jsonify
import requests
import xml.sax.saxutils as saxutils

app = Flask(__name__)

SERVICOS_OFICIAIS = {
    "Workspace": "Workspace",
    "Lighting": "Lighting",
    "ReplicatedFirst": "ReplicatedFirst",
    "ReplicatedStorage": "ReplicatedStorage",
    "ServerScriptService": "ServerScriptService",
    "ServerStorage": "ServerStorage",
    "StarterGui": "StarterGui",
    "StarterPlayer": "StarterPlayer",
    "StarterPack": "StarterPack",
    "Teams": "Teams",
    "SoundService": "SoundService"
}

# Tabela de conversão: Nome do Enum -> Valor Inteiro Oficial no XML do Roblox
MATERIAL_NAME_TO_ID = {
    "Plastic": 256, "SmoothPlastic": 272, "Neon": 288, "Wood": 512, "WoodPlanks": 528,
    "Marble": 784, "Basalt": 788, "Slate": 800, "CrackedLava": 816, "Concrete": 832,
    "Limestone": 848, "Granite": 864, "Pavement": 880, "Brick": 896, "Pebble": 912,
    "Sand": 928, "Glass": 1040, "ForceField": 1056, "Ice": 1072, "Foil": 1088,
    "Metal": 1280, "CorrodedMetal": 1296, "DiamondPlate": 1312, "Fabric": 1328,
    "Grass": 1536, "LeafyGrass": 1552, "Sandstone": 1568, "Mud": 1584,
    "Snow": 1600, "Ground": 1616, "Asphalt": 1792, "Salt": 2048
}

SURFACE_NAME_TO_ID = {
    "Smooth": 0, "Glue": 1, "Weld": 2, "Studs": 3, "Inlet": 4, 
    "Universal": 5, "Hinge": 6, "Motor": 7, "SteppingMotor": 8
}

SHAPE_NAME_TO_ID = {"Ball": 0, "Block": 1, "Cylinder": 2}

def obter_int_do_enum(nome_prop, valor):
    # Case 1: Valor já é um número inteiro enviado pelo Luau
    if isinstance(valor, int):
        return valor

    # Case 2: Valor é um dicionário contendo {"Value": int} ou {"Name": str}
    if isinstance(valor, dict):
        if "Value" in valor and isinstance(valor["Value"], int):
            return valor["Value"]
        if "Name" in valor:
            valor = valor["Name"]

    # Case 3: Valor é uma String (ex: "Enum.Material.Neon" ou "Neon")
    if isinstance(valor, str):
        nome_limpo = valor.split(".")[-1]

        if nome_prop == "Material" and nome_limpo in MATERIAL_NAME_TO_ID:
            return MATERIAL_NAME_TO_ID[nome_limpo]
        
        if nome_prop.endswith("Surface") and nome_limpo in SURFACE_NAME_TO_ID:
            return SURFACE_NAME_TO_ID[nome_limpo]

        if nome_prop in ["Shape", "PartType"] and nome_limpo in SHAPE_NAME_TO_ID:
            return SHAPE_NAME_TO_ID[nome_limpo]

        # Tenta conversão direta caso venha string de número "288"
        if nome_limpo.isdigit():
            return int(nome_limpo)

    return 0

def processar_propriedade_xml(nome_prop, valor, props_dict):
    if valor is None or nome_prop in ["ClassName", "Name", "Parent", "FormFactor"]:
        return ""

    if isinstance(props_dict, dict) and "CFrame" in props_dict and nome_prop in ["Position", "Orientation", "Rotation"]:
        return ""

    # 1. CFRAME
    if nome_prop == "CFrame" and isinstance(valor, list) and len(valor) >= 12:
        return f'''
            <CoordinateFrame name="CFrame">
                <X>{valor[0]}</X><Y>{valor[1]}</Y><Z>{valor[2]}</Z>
                <R00>{valor[3]}</R00><R01>{valor[4]}</R01><R02>{valor[5]}</R02>
                <R10>{valor[6]}</R10><R11>{valor[7]}</R11><R12>{valor[8]}</R12>
                <R20>{valor[9]}</R20><R21>{valor[10]}</R21><R22>{valor[11]}</R22>
            </CoordinateFrame>'''

    # 2. BOOLEANOS
    if isinstance(valor, bool):
        val_str = "true" if valor else "false"
        return f'\n            <bool name="{nome_prop}">{val_str}</bool>'

    # 3. ENUMS (Garante conversão estrita para número inteiro dentro da tag <token>)
    e_enum = (
        nome_prop in ["Material", "Shape", "Font", "PartType"] or
        nome_prop.endswith("Surface") or
        nome_prop.endswith("Type") or 
        nome_prop.endswith("Style") or 
        nome_prop.endswith("Mode") or 
        nome_prop.endswith("Alignment") or 
        nome_prop.endswith("Direction")
    )

    if e_enum or (isinstance(valor, str) and "Enum." in valor):
        enum_int_val = obter_int_do_enum(nome_prop, valor)
        return f'\n            <token name="{nome_prop}">{enum_int_val}</token>'

    # 4. INTEIROS
    if isinstance(valor, int):
        return f'\n            <int name="{nome_prop}">{valor}</int>'

    # 5. FLOATS
    if isinstance(valor, float):
        return f'\n            <float name="{nome_prop}">{float(valor)}</float>'

    # 6. DICIONÁRIOS (UDim2, Vector3, Color3)
    if isinstance(valor, dict):
        if "X" in valor and "Y" in valor and isinstance(valor.get("X"), dict):
            x_dict, y_dict = valor.get("X", {}), valor.get("Y", {})
            return f'''
            <UDim2 name="{nome_prop}">
                <XS>{x_dict.get("Scale", 0)}</XS>
                <XO>{x_dict.get("Offset", 0)}</XO>
                <YS>{y_dict.get("Scale", 0)}</YS>
                <YO>{y_dict.get("Offset", 0)}</YO>
            </UDim2>'''

        if "X" in valor and "Y" in valor and "Z" in valor:
            return f'''
            <Vector3 name="{nome_prop}">
                <X>{valor.get("X", 0)}</X><Y>{valor.get("Y", 0)}</Y><Z>{valor.get("Z", 0)}</Z>
            </Vector3>'''

        if "R" in valor and "G" in valor and "B" in valor:
            r = valor["R"] / 255.0 if valor["R"] > 1.0 else valor["R"]
            g = valor["G"] / 255.0 if valor["G"] > 1.0 else valor["G"]
            b = valor["B"] / 255.0 if valor["B"] > 1.0 else valor["B"]
            return f'''
            <Color3 name="{nome_prop}">
                <R>{r}</R>
                <G>{g}</G>
                <B>{b}</B>
            </Color3>'''

    # 7. STRINGS E CONTEÚDOS DE MÍDIA
    if isinstance(valor, str):
        if nome_prop in ["Texture", "Image", "TextureId", "ImageId", "MeshId", "SoundId"] or valor.startswith("rbxassetid://"):
            return f'\n            <Content name="{nome_prop}"><url>{saxutils.escape(valor)}</url></Content>'

        return f'\n            <string name="{nome_prop}">{saxutils.escape(valor)}</string>'

    return ""

def processar_objetos_xml(TableData):
    xml_output = ""

    if isinstance(TableData, list):
        for idx, a in enumerate(TableData):
            if isinstance(a, dict):
                props = a.get("Properties", {})
                children = a.get("Children", [])
                script_code = a.get("Script")

                if not isinstance(props, dict):
                    props = {}

                class_name = props.get("ClassName", "Part")
                obj_name = props.get("Name", f"Object_{idx}")

                if script_code and class_name not in ["Script", "LocalScript", "ModuleScript"]:
                    class_name = "Script"

                ref_id = f"RBX_OBJ_{idx}_{abs(hash(obj_name))}"

                xml_output += f'\n<Item class="{class_name}" referent="{ref_id}">'
                xml_output += '\n  <Properties>'
                xml_output += f'\n    <string name="Name">{saxutils.escape(str(obj_name))}</string>'

                if class_name == "ScreenGui":
                    if "ResetOnSpawn" not in props:
                        props["ResetOnSpawn"] = True
                    if "Enabled" not in props:
                        props["Enabled"] = True

                if class_name in ["Part", "WedgePart", "CornerWedgePart", "MeshPart", "SpawnLocation", "BasePart"]:
                    if "Anchored" not in props:
                        props["Anchored"] = True
                    if "CanCollide" not in props:
                        props["CanCollide"] = True

                for nome_prop, val_prop in props.items():
                    xml_output += processar_propriedade_xml(nome_prop, val_prop, props)

                if script_code or class_name in ["Script", "LocalScript", "ModuleScript"]:
                    codigo_str = str(script_code) if script_code is not None else ""
                    codigo_escapado = saxutils.escape(codigo_str)
                    xml_output += f'\n            <ProtectedString name="Source">{codigo_escapado}</ProtectedString>'

                xml_output += '\n  </Properties>'

                if children and isinstance(children, list):
                    xml_output += processar_objetos_xml(children)

                xml_output += '\n</Item>'

    return xml_output

def construir_rbxlx_completo(part_data_dict):
    workspace_content = ""
    outros_servicos = ""

    if isinstance(part_data_dict, dict):
        for servico_nome, servico_dados in part_data_dict.items():
            objetos = servico_dados.get("Objects", []) if isinstance(servico_dados, dict) else servico_dados

            if servico_nome == "Workspace":
                workspace_content += processar_objetos_xml(objetos)
            else:
                classe_servico = SERVICOS_OFICIAIS.get(servico_nome, "Folder")
                ref_servico = f"RBX_SERVICE_{servico_nome.upper()}"

                outros_servicos += f'\n<Item class="{classe_servico}" referent="{ref_servico}">'
                outros_servicos += f'\n  <Properties><string name="Name">{servico_nome}</string></Properties>'
                outros_servicos += processar_objetos_xml(objetos)
                outros_servicos += '\n</Item>'

    elif isinstance(part_data_dict, list):
        workspace_content = processar_objetos_xml(part_data_dict)

    rbxlx_str = f'''<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">
    <External>null</External>
    <External>nil</External>
    <Item class="Workspace" referent="RBX_WORKSPACE_ROOT">
        <Properties>
            <string name="Name">Workspace</string>
            <bool name="FilteringEnabled">true</bool>
        </Properties>
        {workspace_content}
    </Item>
    {outros_servicos}
</roblox>'''

    return rbxlx_str.encode('utf-8')

@app.route('/publicar', methods=['POST'])
def publicar():
    try:
        dados_json = request.json
        api_key = request.headers.get('x-api-key')
        universe_id = request.headers.get('universe-id')
        place_id = request.headers.get('place-id')

        if not api_key or not universe_id or not place_id:
            return jsonify({"erro": "Headers obrigatorios faltando."}), 400

        conteudo_rbxlx = construir_rbxlx_completo(dados_json)
        url_roblox = f"https://apis.roblox.com/universes/v1/{universe_id}/places/{place_id}/versions?versionType=Published"

        headers_roblox = {
            "x-api-key": api_key,
            "Content-Type": "application/xml",
            "User-Agent": "RobloxOpenCloudClient/1.0"
        }

        resposta = requests.post(url_roblox, headers=headers_roblox, data=conteudo_rbxlx)

        return jsonify({
            "status": resposta.status_code,
            "resposta_roblox": resposta.text
        })

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
